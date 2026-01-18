"""
Enhanced Autonomous Chat Service with Real-time Capabilities.

This service provides an improved autonomous chat experience with:
- Real-time WebSocket communication
- Maximum 2 clarification rounds
- Intelligent prompt analysis
- Streaming responses
- Enhanced error handling
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.chat.autonomous_chat_service import (
    AutonomousChatService, 
    PromptAnalysis, 
    ClarificationRequest,
    AutonomousChatServiceError
)
from app.services.websocket_manager import websocket_manager
from app.services.code_generation.llm_providers.provider_factory import ProviderFactory
from app.services.code_generation.config.settings import get_code_generation_settings
from app.models.chat import MessageType, ConversationThread, ProjectChat
from logconfig.logger import get_logger

logger = get_logger()
settings = get_code_generation_settings()


@dataclass
class EnhancedPromptAnalysis(PromptAnalysis):
    """Enhanced prompt analysis with real-time capabilities."""
    processing_time_ms: int = 0
    requires_immediate_clarification: bool = False
    clarification_priority: str = "normal"  # low, normal, high, critical
    estimated_generation_time: int = 60  # seconds
    complexity_score: float = 0.5  # 0.0-1.0
    is_conversational: bool = False  # True if this is a follow-up conversation
    conversation_type: str = "generation"  # generation, question, modification, discussion


@dataclass
class RealTimeClarificationRequest(ClarificationRequest):
    """Real-time clarification request with enhanced features."""
    max_rounds: int = 2
    current_round: int = 1
    timeout_seconds: int = 300  # 5 minutes
    auto_proceed_after_timeout: bool = True
    priority_questions: List[str] = field(default_factory=list)
    optional_questions: List[str] = field(default_factory=list)


class EnhancedAutonomousChatService(AutonomousChatService):
    """
    Enhanced autonomous chat service with real-time capabilities.
    
    Features:
    - Maximum 2 clarification rounds
    - Real-time WebSocket communication
    - Streaming responses
    - Intelligent timeout handling
    - Enhanced error recovery
    """

    def __init__(self, db_session: AsyncSession):
        """Initialize the enhanced autonomous chat service."""
        super().__init__(db_session)
        self.max_clarification_rounds = 2
        self.default_timeout = 300  # 5 minutes
        self.active_conversations: Dict[str, Dict[str, Any]] = {}
        
        logger.info("EnhancedAutonomousChatService initialized with real-time capabilities")

    async def process_message_with_realtime(
        self,
        project_id: str,
        user_id: str,
        message_content: str,
        thread_id: Optional[str] = None,
        cloud_provider: str = "AWS",
        conversation_mode: str = "auto"  # auto, generation_only, chat_only
    ) -> Dict[str, Any]:
        """
        Process a user message with real-time updates and enhanced flow.

        Args:
            project_id: ID of the project
            user_id: User ID sending the message
            message_content: The user's message
            thread_id: Optional existing thread ID
            cloud_provider: Cloud provider for infrastructure

        Returns:
            Dict[str, Any]: Processing result with real-time job information
        """
        try:
            start_time = datetime.utcnow()
            
            # Create or get thread
            if not thread_id:
                thread_id = await self._create_enhanced_thread(
                    project_id, user_id, cloud_provider
                )
            
            # Initialize conversation tracking
            conversation_key = f"{thread_id}_{user_id}"
            self.active_conversations[conversation_key] = {
                "thread_id": thread_id,
                "user_id": user_id,
                "project_id": project_id,
                "clarification_round": 0,
                "start_time": start_time,
                "last_activity": start_time
            }

            # Send real-time notification that processing started
            await self._notify_processing_started(user_id, thread_id, project_id)

            # Analyze prompt with enhanced capabilities
            analysis = await self._analyze_prompt_enhanced(
                message_content, thread_id, user_id
            )

            # Update conversation state
            self.active_conversations[conversation_key]["analysis"] = analysis

            # Determine next action based on analysis and conversation mode
            if analysis.is_conversational and conversation_mode != "generation_only":
                # Handle as conversational message
                return await self.process_conversational_message(
                    project_id, user_id, message_content, thread_id,
                    conversation_context=self.active_conversations[conversation_key]
                )
            elif analysis.conversation_type == "generation" or conversation_mode == "generation_only":
                # Handle as code generation request
                if analysis.requires_immediate_clarification and analysis.clarification_needed:
                    return await self._handle_clarification_flow(
                        conversation_key, message_content, analysis
                    )
                elif analysis.is_complete or analysis.confidence_score >= 0.8:
                    return await self._trigger_enhanced_generation(
                        conversation_key, message_content
                    )
                else:
                    return await self._handle_clarification_flow(
                        conversation_key, message_content, analysis
                    )
            else:
                # Auto-detect: could be either conversational or generation
                if analysis.confidence_score >= 0.6:
                    # High confidence it's a generation request
                    return await self._trigger_enhanced_generation(
                        conversation_key, message_content
                    )
                else:
                    # Treat as conversational first, offer generation option
                    return await self.process_conversational_message(
                        project_id, user_id, message_content, thread_id,
                        conversation_context=self.active_conversations[conversation_key]
                    )

        except Exception as e:
            logger.error(f"Error in enhanced message processing: {e}")
            await self._notify_error(user_id, thread_id, str(e))
            raise AutonomousChatServiceError(f"Enhanced processing failed: {e}")

    async def _analyze_prompt_enhanced(
        self,
        prompt: str,
        thread_id: str,
        user_id: str
    ) -> EnhancedPromptAnalysis:
        """
        Analyze prompt with enhanced real-time capabilities.

        Args:
            prompt: User's prompt
            thread_id: Conversation thread ID
            user_id: User ID for real-time updates

        Returns:
            EnhancedPromptAnalysis: Enhanced analysis result
        """
        start_time = datetime.utcnow()
        
        # Send real-time update
        await websocket_manager.send_to_user(user_id, {
            "type": "analysis_started",
            "thread_id": thread_id,
            "message": "Analyzing your request...",
            "timestamp": start_time.isoformat()
        })

        try:
            # Get base analysis
            base_analysis = await self.analyze_prompt_completeness(prompt, thread_id)
            
            # Calculate processing time
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Enhanced analysis with conversation detection
            is_conversational, conversation_type = self._detect_conversation_type(prompt, thread_id)
            
            enhanced_analysis = EnhancedPromptAnalysis(
                is_complete=base_analysis.is_complete,
                confidence_score=base_analysis.confidence_score,
                missing_elements=base_analysis.missing_elements,
                clarification_needed=base_analysis.clarification_needed,
                suggested_questions=base_analysis.suggested_questions,
                intent_classification=base_analysis.intent_classification,
                analysis_metadata=base_analysis.analysis_metadata,
                processing_time_ms=int(processing_time),
                requires_immediate_clarification=self._requires_immediate_clarification(base_analysis),
                clarification_priority=self._determine_clarification_priority(base_analysis),
                estimated_generation_time=self._estimate_generation_time(prompt, base_analysis),
                complexity_score=self._calculate_complexity_score(prompt, base_analysis),
                is_conversational=is_conversational,
                conversation_type=conversation_type
            )

            # Send analysis complete notification
            await websocket_manager.send_to_user(user_id, {
                "type": "analysis_complete",
                "thread_id": thread_id,
                "analysis": {
                    "is_complete": enhanced_analysis.is_complete,
                    "confidence_score": enhanced_analysis.confidence_score,
                    "complexity_score": enhanced_analysis.complexity_score,
                    "estimated_time": enhanced_analysis.estimated_generation_time
                },
                "message": f"Analysis complete (confidence: {enhanced_analysis.confidence_score:.1%})",
                "timestamp": datetime.utcnow().isoformat()
            })

            return enhanced_analysis

        except Exception as e:
            await websocket_manager.send_to_user(user_id, {
                "type": "analysis_error",
                "thread_id": thread_id,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            })
            raise

    async def _handle_clarification_flow(
        self,
        conversation_key: str,
        original_message: str,
        analysis: EnhancedPromptAnalysis
    ) -> Dict[str, Any]:
        """
        Handle the clarification flow with maximum 2 rounds.

        Args:
            conversation_key: Conversation tracking key
            original_message: Original user message
            analysis: Enhanced prompt analysis

        Returns:
            Dict[str, Any]: Clarification flow result
        """
        conversation = self.active_conversations[conversation_key]
        current_round = conversation["clarification_round"]
        
        # Check if we've reached max clarification rounds
        if current_round >= self.max_clarification_rounds:
            logger.info(f"Max clarification rounds reached for {conversation_key}, proceeding with generation")
            return await self._trigger_enhanced_generation(
                conversation_key, 
                f"[After {self.max_clarification_rounds} clarification rounds] {original_message}"
            )

        # Generate clarification questions
        questions = await self._generate_enhanced_clarification_questions(
            original_message, analysis, current_round + 1
        )

        if not questions:
            # No questions generated, proceed with generation
            return await self._trigger_enhanced_generation(conversation_key, original_message)

        # Create enhanced clarification request
        clarification_request = await self._create_enhanced_clarification_request(
            conversation["thread_id"],
            questions,
            current_round + 1,
            analysis
        )

        # Update conversation state
        conversation["clarification_round"] = current_round + 1
        conversation["clarification_request"] = clarification_request
        conversation["last_activity"] = datetime.utcnow()

        # Send real-time clarification request
        await self._send_realtime_clarification_request(
            conversation["user_id"],
            clarification_request
        )

        return {
            "thread_id": conversation["thread_id"],
            "status": "clarification_requested",
            "clarification_request": {
                "id": clarification_request.request_id,
                "questions": clarification_request.questions,
                "round": current_round + 1,
                "max_rounds": self.max_clarification_rounds,
                "timeout_seconds": clarification_request.timeout_seconds
            },
            "next_action": "await_clarification_response"
        }

    async def _generate_enhanced_clarification_questions(
        self,
        prompt: str,
        analysis: EnhancedPromptAnalysis,
        round_number: int
    ) -> List[str]:
        """
        Generate enhanced clarification questions based on round number and priority.

        Args:
            prompt: Original prompt
            analysis: Enhanced analysis
            round_number: Current clarification round (1 or 2)

        Returns:
            List[str]: Prioritized clarification questions
        """
        if round_number == 1:
            # First round: Focus on critical missing elements
            critical_elements = [elem for elem in analysis.missing_elements 
                               if any(keyword in elem.lower() for keyword in 
                                     ['provider', 'region', 'type', 'size', 'network'])]
            
            if critical_elements:
                questions = await self.generate_clarification_questions(
                    prompt, analysis, None
                )
                # Limit to 2 most critical questions for first round
                return questions[:2]
        
        elif round_number == 2:
            # Second round: Focus on remaining essential details
            remaining_elements = [elem for elem in analysis.missing_elements 
                                if not any(keyword in elem.lower() for keyword in 
                                          ['provider', 'region', 'type', 'size'])]
            
            if remaining_elements:
                # Generate more specific questions for second round
                enhanced_prompt = f"""
                This is the FINAL clarification round (2 of 2). Generate 1-2 essential questions 
                that are absolutely necessary for code generation.

                Original request: "{prompt}"
                Remaining missing elements: {remaining_elements}

                Focus only on details that would prevent successful code generation.
                """
                
                questions = await self._generate_questions_with_prompt(enhanced_prompt)
                return questions[:1]  # Only 1 question for final round

        return []

    async def _create_enhanced_clarification_request(
        self,
        thread_id: str,
        questions: List[str],
        round_number: int,
        analysis: EnhancedPromptAnalysis
    ) -> RealTimeClarificationRequest:
        """
        Create an enhanced clarification request with real-time features.

        Args:
            thread_id: Conversation thread ID
            questions: List of clarification questions
            round_number: Current round number
            analysis: Enhanced analysis

        Returns:
            RealTimeClarificationRequest: Enhanced clarification request
        """
        # Determine timeout based on priority and round
        timeout = self.default_timeout
        if analysis.clarification_priority == "critical":
            timeout = 600  # 10 minutes for critical
        elif round_number == 2:
            timeout = 180  # 3 minutes for final round

        context_summary = await self.context_manager.summarize_context(thread_id)

        request = RealTimeClarificationRequest(
            request_id=str(uuid.uuid4()),
            thread_id=thread_id,
            questions=questions,
            context_summary=context_summary,
            created_at=datetime.utcnow(),
            max_rounds=self.max_clarification_rounds,
            current_round=round_number,
            timeout_seconds=timeout,
            auto_proceed_after_timeout=True,
            priority_questions=questions,  # All questions are priority in enhanced mode
            optional_questions=[]
        )

        # Store in active clarifications
        self.active_clarifications[request.request_id] = request

        # Set up automatic timeout handling
        asyncio.create_task(self._handle_enhanced_timeout(request))

        return request

    async def _send_realtime_clarification_request(
        self,
        user_id: str,
        request: RealTimeClarificationRequest
    ) -> None:
        """
        Send real-time clarification request to user.

        Args:
            user_id: User ID to send to
            request: Clarification request
        """
        message_text = self._format_clarification_message(request)
        
        await websocket_manager.send_to_user(user_id, {
            "type": "clarification_needed",
            "thread_id": request.thread_id,
            "clarification_id": request.request_id,
            "questions": request.questions,
            "round": request.current_round,
            "max_rounds": request.max_rounds,
            "timeout_seconds": request.timeout_seconds,
            "priority": "high" if request.current_round == 2 else "normal",
            "message": message_text,
            "timestamp": datetime.utcnow().isoformat()
        })

    def _format_clarification_message(self, request: RealTimeClarificationRequest) -> str:
        """Format clarification message for user display."""
        round_text = f"Round {request.current_round} of {request.max_rounds}"
        
        if request.current_round == 1:
            intro = f"I need some clarification to generate the best code for you. ({round_text})"
        else:
            intro = f"Final clarification needed to complete your request. ({round_text})"
        
        questions_text = "\n".join([f"{i+1}. {q}" for i, q in enumerate(request.questions)])
        
        timeout_text = f"Please respond within {request.timeout_seconds // 60} minutes."
        
        return f"{intro}\n\n{questions_text}\n\n{timeout_text}"

    async def _handle_enhanced_timeout(self, request: RealTimeClarificationRequest) -> None:
        """
        Handle timeout for enhanced clarification requests.

        Args:
            request: Clarification request to handle timeout for
        """
        try:
            await asyncio.sleep(request.timeout_seconds)
            
            if request.request_id in self.active_clarifications:
                # Find conversation and proceed with generation
                conversation_key = None
                for key, conv in self.active_conversations.items():
                    if conv.get("thread_id") == request.thread_id:
                        conversation_key = key
                        break
                
                if conversation_key and request.auto_proceed_after_timeout:
                    logger.info(f"Clarification timeout for {request.request_id}, proceeding with generation")
                    
                    # Notify user about timeout
                    conversation = self.active_conversations[conversation_key]
                    await websocket_manager.send_to_user(conversation["user_id"], {
                        "type": "clarification_timeout",
                        "thread_id": request.thread_id,
                        "clarification_id": request.request_id,
                        "message": "Clarification timeout reached. Proceeding with available information.",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    
                    # Proceed with generation using available information
                    await self._trigger_enhanced_generation(
                        conversation_key,
                        f"[Timeout after {request.timeout_seconds}s] {conversation.get('original_message', 'User request')}"
                    )
                
                # Clean up
                if request.request_id in self.active_clarifications:
                    del self.active_clarifications[request.request_id]
                    
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error handling clarification timeout: {e}")

    async def process_clarification_response_enhanced(
        self,
        project_id: str,
        user_id: str,
        clarification_id: str,
        responses: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Process clarification response with enhanced real-time flow.

        Args:
            project_id: Project ID
            user_id: User ID responding
            clarification_id: Clarification request ID
            responses: User responses to questions

        Returns:
            Dict[str, Any]: Processing result
        """
        try:
            # Find the clarification request
            if clarification_id not in self.active_clarifications:
                raise AutonomousChatServiceError(f"Clarification request {clarification_id} not found")

            request = self.active_clarifications[clarification_id]
            
            # Find conversation
            conversation_key = None
            for key, conv in self.active_conversations.items():
                if conv.get("thread_id") == request.thread_id and conv.get("user_id") == user_id:
                    conversation_key = key
                    break
            
            if not conversation_key:
                raise AutonomousChatServiceError("Conversation not found")

            conversation = self.active_conversations[conversation_key]

            # Send acknowledgment
            await websocket_manager.send_to_user(user_id, {
                "type": "clarification_received",
                "thread_id": request.thread_id,
                "clarification_id": clarification_id,
                "message": "Processing your clarification...",
                "timestamp": datetime.utcnow().isoformat()
            })

            # Process the response
            enriched_prompt = await self._enrich_prompt_with_responses(
                request, responses, conversation
            )

            # Re-analyze with enriched prompt
            enhanced_analysis = await self._analyze_prompt_enhanced(
                enriched_prompt, request.thread_id, user_id
            )

            # Update conversation
            conversation["clarification_responses"] = responses
            conversation["enriched_prompt"] = enriched_prompt
            conversation["last_activity"] = datetime.utcnow()

            # Clean up clarification request
            del self.active_clarifications[clarification_id]

            # Determine next action
            if (enhanced_analysis.is_complete or 
                enhanced_analysis.confidence_score >= 0.7 or 
                conversation["clarification_round"] >= self.max_clarification_rounds):
                
                # Proceed with generation
                return await self._trigger_enhanced_generation(conversation_key, enriched_prompt)
            else:
                # Need another clarification round
                return await self._handle_clarification_flow(
                    conversation_key, enriched_prompt, enhanced_analysis
                )

        except Exception as e:
            logger.error(f"Error processing enhanced clarification response: {e}")
            await self._notify_error(user_id, request.thread_id if 'request' in locals() else None, str(e))
            raise

    async def _trigger_enhanced_generation(
        self,
        conversation_key: str,
        final_prompt: str
    ) -> Dict[str, Any]:
        """
        Trigger enhanced code generation with real-time updates and Azure File Share integration.

        Args:
            conversation_key: Conversation tracking key
            final_prompt: Final enriched prompt for generation

        Returns:
            Dict[str, Any]: Generation result
        """
        conversation = self.active_conversations[conversation_key]
        
        try:
            # Send generation started notification
            await websocket_manager.send_to_user(conversation["user_id"], {
                "type": "generation_started",
                "thread_id": conversation["thread_id"],
                "project_id": conversation["project_id"],
                "message": "Starting code generation with your requirements...",
                "estimated_time": conversation.get("analysis", {}).get("estimated_generation_time", 60),
                "timestamp": datetime.utcnow().isoformat()
            })

            # Trigger generation using parent class method
            generation_result = await self.trigger_code_generation(
                thread_id=conversation["thread_id"],
                enriched_prompt=final_prompt,
                user_id=conversation["user_id"],
                project_id=conversation["project_id"]
            )

            # Update conversation state
            conversation["generation_triggered"] = True
            conversation["generation_result"] = generation_result
            conversation["status"] = "generating"

            # Start monitoring generation progress and handle Azure File Share saving
            asyncio.create_task(self._monitor_generation_with_azure_save(
                conversation_key, generation_result
            ))

            return {
                "thread_id": conversation["thread_id"],
                "status": "generation_started",
                "job_id": generation_result["job_id"],
                "generation_id": generation_result["generation_id"],
                "estimated_completion": generation_result.get("estimated_completion"),
                "next_action": "monitor_generation",
                "azure_integration": True
            }

        except Exception as e:
            logger.error(f"Error triggering enhanced generation: {e}")
            await self._notify_error(conversation["user_id"], conversation["thread_id"], str(e))
            raise

    async def _monitor_generation_with_azure_save(
        self,
        conversation_key: str,
        generation_result: Dict[str, Any]
    ) -> None:
        """
        Monitor code generation progress and automatically save to Azure File Share.

        Args:
            conversation_key: Conversation tracking key
            generation_result: Generation result from orchestrator
        """
        conversation = self.active_conversations[conversation_key]
        
        try:
            from app.services.azure_file_service import get_azure_file_service
            
            # Get Azure File Service
            azure_service = await get_azure_file_service()
            
            # Monitor generation progress
            job_id = generation_result["job_id"]
            generation_id = generation_result["generation_id"]
            
            # Poll for completion (in real implementation, this would be event-driven)
            max_wait_time = 300  # 5 minutes
            poll_interval = 5    # 5 seconds
            elapsed_time = 0
            
            while elapsed_time < max_wait_time:
                try:
                    # Check generation status
                    status = await self._check_generation_status(job_id)
                    
                    if status["status"] == "completed":
                        # Generation completed, save to Azure
                        await self._save_generated_files_to_azure(
                            conversation_key, 
                            status["generated_files"],
                            azure_service
                        )
                        break
                    elif status["status"] == "failed":
                        # Generation failed
                        await self._handle_generation_failure(
                            conversation_key, 
                            status.get("error", "Generation failed")
                        )
                        break
                    else:
                        # Still generating, send progress update
                        await websocket_manager.send_to_user(conversation["user_id"], {
                            "type": "generation_progress",
                            "thread_id": conversation["thread_id"],
                            "job_id": job_id,
                            "status": status["status"],
                            "progress_percentage": status.get("progress", 0),
                            "current_step": status.get("current_step", "Generating code..."),
                            "timestamp": datetime.utcnow().isoformat()
                        })
                
                except Exception as e:
                    logger.error(f"Error checking generation status: {e}")
                
                await asyncio.sleep(poll_interval)
                elapsed_time += poll_interval
            
            if elapsed_time >= max_wait_time:
                await self._handle_generation_timeout(conversation_key)
                
        except Exception as e:
            logger.error(f"Error monitoring generation: {e}")
            await self._handle_generation_failure(conversation_key, str(e))

    async def _save_generated_files_to_azure(
        self,
        conversation_key: str,
        generated_files: Dict[str, str],
        azure_service
    ) -> None:
        """
        Save generated files to Azure File Share with user isolation.

        Args:
            conversation_key: Conversation tracking key
            generated_files: Dictionary of filename -> content
            azure_service: Azure File Service instance
        """
        conversation = self.active_conversations[conversation_key]
        
        try:
            # Send saving notification
            await websocket_manager.send_to_user(conversation["user_id"], {
                "type": "saving_to_azure",
                "thread_id": conversation["thread_id"],
                "message": f"Saving {len(generated_files)} files to Azure File Share...",
                "file_count": len(generated_files),
                "timestamp": datetime.utcnow().isoformat()
            })

            # Save files to Azure with user isolation
            save_result = await azure_service.save_generated_files(
                user_id=conversation["user_id"],
                project_id=conversation["project_id"],
                generation_id=conversation["generation_result"]["generation_id"],
                files=generated_files
            )

            if save_result.success:
                # Files saved successfully
                conversation["azure_save_result"] = save_result
                conversation["status"] = "complete"
                
                await websocket_manager.send_to_user(conversation["user_id"], {
                    "type": "generation_completed",
                    "thread_id": conversation["thread_id"],
                    "generation_id": conversation["generation_result"]["generation_id"],
                    "files_generated": list(generated_files.keys()),
                    "files_saved": save_result.saved_files,
                    "azure_paths": save_result.azure_paths,
                    "message": f"✅ Generated and saved {len(save_result.saved_files)} files to Azure File Share!",
                    "azure_location": f"projects/{conversation['user_id']}/{conversation['project_id']}/{conversation['generation_result']['generation_id']}/",
                    "timestamp": datetime.utcnow().isoformat()
                })
                
                # Send file details
                await websocket_manager.send_to_user(conversation["user_id"], {
                    "type": "azure_files_saved",
                    "thread_id": conversation["thread_id"],
                    "saved_files": [
                        {
                            "filename": filename,
                            "azure_path": path,
                            "size": len(generated_files.get(filename, "")),
                            "content_preview": generated_files.get(filename, "")[:200] + "..." if len(generated_files.get(filename, "")) > 200 else generated_files.get(filename, "")
                        }
                        for filename, path in zip(save_result.saved_files, save_result.azure_paths)
                    ],
                    "access_info": {
                        "share_name": azure_service.config.AZURE_FILE_SHARE_NAME,
                        "user_path": f"projects/{conversation['user_id']}/{conversation['project_id']}/",
                        "generation_path": f"projects/{conversation['user_id']}/{conversation['project_id']}/{conversation['generation_result']['generation_id']}/"
                    },
                    "timestamp": datetime.utcnow().isoformat()
                })
                
            else:
                # Some or all files failed to save
                await websocket_manager.send_to_user(conversation["user_id"], {
                    "type": "azure_save_error",
                    "thread_id": conversation["thread_id"],
                    "error": save_result.error,
                    "saved_files": save_result.saved_files,
                    "failed_files": save_result.failed_files,
                    "message": f"⚠️ Saved {len(save_result.saved_files)} files, but {len(save_result.failed_files)} failed",
                    "timestamp": datetime.utcnow().isoformat()
                })

        except Exception as e:
            logger.error(f"Error saving files to Azure: {e}")
            await websocket_manager.send_to_user(conversation["user_id"], {
                "type": "azure_save_error",
                "thread_id": conversation["thread_id"],
                "error": str(e),
                "message": "❌ Failed to save files to Azure File Share",
                "timestamp": datetime.utcnow().isoformat()
            })

    async def _check_generation_status(self, job_id: str) -> Dict[str, Any]:
        """
        Check the status of a code generation job.

        Args:
            job_id: Job identifier

        Returns:
            Dict with status information
        """
        try:
            # This would integrate with your actual job monitoring system
            # For now, we'll simulate the check
            status = await self.code_orchestrator.get_job_status(job_id)
            return status
        except Exception as e:
            logger.error(f"Error checking job status {job_id}: {e}")
            return {"status": "error", "error": str(e)}

    async def _handle_generation_failure(
        self,
        conversation_key: str,
        error_message: str
    ) -> None:
        """Handle generation failure."""
        conversation = self.active_conversations[conversation_key]
        conversation["status"] = "error"
        
        await websocket_manager.send_to_user(conversation["user_id"], {
            "type": "generation_failed",
            "thread_id": conversation["thread_id"],
            "error": error_message,
            "message": f"❌ Code generation failed: {error_message}",
            "timestamp": datetime.utcnow().isoformat()
        })

    async def _handle_generation_timeout(self, conversation_key: str) -> None:
        """Handle generation timeout."""
        conversation = self.active_conversations[conversation_key]
        conversation["status"] = "error"
        
        await websocket_manager.send_to_user(conversation["user_id"], {
            "type": "generation_timeout",
            "thread_id": conversation["thread_id"],
            "message": "⏰ Code generation timed out. Please try again.",
            "timestamp": datetime.utcnow().isoformat()
        })

    # Helper methods
    async def _create_enhanced_thread(
        self, project_id: str, user_id: str, cloud_provider: str
    ) -> str:
        """Create an enhanced conversation thread."""
        thread_id = str(uuid.uuid4())
        
        # Create thread record
        thread = ConversationThread(
            id=thread_id,
            project_id=project_id,
            user_id=user_id,
            cloud_provider=cloud_provider,
            status="active",
            title=f"Enhanced Chat - {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
        )
        
        self.db.add(thread)
        await self.db.flush()
        
        return thread_id

    async def _notify_processing_started(
        self, user_id: str, thread_id: str, project_id: str
    ) -> None:
        """Send processing started notification."""
        await websocket_manager.send_to_user(user_id, {
            "type": "processing_started",
            "thread_id": thread_id,
            "project_id": project_id,
            "message": "Processing your request...",
            "timestamp": datetime.utcnow().isoformat()
        })

    async def _notify_error(
        self, user_id: str, thread_id: Optional[str], error_message: str
    ) -> None:
        """Send error notification to user."""
        await websocket_manager.send_to_user(user_id, {
            "type": "error",
            "thread_id": thread_id,
            "error": error_message,
            "message": "An error occurred while processing your request.",
            "timestamp": datetime.utcnow().isoformat()
        })

    def _requires_immediate_clarification(self, analysis: PromptAnalysis) -> bool:
        """Determine if immediate clarification is required."""
        critical_missing = any(
            keyword in " ".join(analysis.missing_elements).lower()
            for keyword in ["provider", "region", "critical", "essential"]
        )
        return analysis.confidence_score < 0.3 or critical_missing

    def _determine_clarification_priority(self, analysis: PromptAnalysis) -> str:
        """Determine clarification priority level."""
        if analysis.confidence_score < 0.2:
            return "critical"
        elif analysis.confidence_score < 0.5:
            return "high"
        elif analysis.confidence_score < 0.7:
            return "normal"
        else:
            return "low"

    def _estimate_generation_time(self, prompt: str, analysis: PromptAnalysis) -> int:
        """Estimate code generation time in seconds."""
        base_time = 30
        
        # Adjust based on complexity
        if len(prompt.split()) > 50:
            base_time += 30
        
        if analysis.confidence_score < 0.5:
            base_time += 20
        
        # Adjust based on missing elements
        base_time += len(analysis.missing_elements) * 10
        
        return min(base_time, 180)  # Cap at 3 minutes

    def _calculate_complexity_score(self, prompt: str, analysis: PromptAnalysis) -> float:
        """Calculate complexity score for the request."""
        score = 0.5  # Base score
        
        # Adjust based on prompt length
        word_count = len(prompt.split())
        if word_count > 100:
            score += 0.2
        elif word_count < 20:
            score -= 0.1
        
        # Adjust based on missing elements
        missing_count = len(analysis.missing_elements)
        if missing_count > 5:
            score += 0.2
        elif missing_count < 2:
            score -= 0.1
        
        # Adjust based on confidence
        score += (1 - analysis.confidence_score) * 0.3
        
        return max(0.0, min(1.0, score))

    def _detect_conversation_type(self, prompt: str, thread_id: str) -> Tuple[bool, str]:
        """
        Detect if this is a conversational message or a generation request.
        
        Returns:
            Tuple[bool, str]: (is_conversational, conversation_type)
        """
        prompt_lower = prompt.lower()
        
        # Check for explicit generation keywords
        generation_keywords = [
            "create", "generate", "build", "set up", "deploy", "provision", 
            "configure", "implement", "establish", "launch", "spin up"
        ]
        
        # Check for conversational keywords
        conversational_keywords = [
            "explain", "what is", "how does", "why", "tell me", "can you help",
            "what about", "how about", "what if", "should i", "would you recommend"
        ]
        
        # Check for modification keywords
        modification_keywords = [
            "change", "modify", "update", "alter", "adjust", "improve", 
            "optimize", "fix", "correct", "enhance"
        ]
        
        # Check for question patterns
        question_patterns = ["?", "how", "what", "why", "when", "where", "which"]
        
        # Score different types
        generation_score = sum(1 for keyword in generation_keywords if keyword in prompt_lower)
        conversational_score = sum(1 for keyword in conversational_keywords if keyword in prompt_lower)
        modification_score = sum(1 for keyword in modification_keywords if keyword in prompt_lower)
        question_score = sum(1 for pattern in question_patterns if pattern in prompt_lower)
        
        # Check if there's existing conversation context
        conversation_key = f"{thread_id}_*" if thread_id else None
        has_context = False
        if conversation_key:
            for key in self.active_conversations:
                if key.startswith(f"{thread_id}_"):
                    has_context = True
                    break
        
        # Determine conversation type
        if generation_score >= 2 or (generation_score >= 1 and not has_context):
            return False, "generation"
        elif modification_score >= 1 and has_context:
            return True, "modification"
        elif conversational_score >= 1 or question_score >= 2:
            return True, "question"
        elif has_context and (question_score >= 1 or len(prompt.split()) < 10):
            return True, "discussion"
        elif generation_score >= 1:
            return False, "generation"
        else:
            # Default: treat short messages as conversational, longer as generation
            if len(prompt.split()) <= 5:
                return True, "discussion"
            else:
                return False, "generation"

    async def _enrich_prompt_with_responses(
        self,
        request: RealTimeClarificationRequest,
        responses: Dict[str, str],
        conversation: Dict[str, Any]
    ) -> str:
        """Enrich prompt with clarification responses."""
        base_prompt = conversation.get("enriched_prompt") or conversation.get("original_message", "")
        
        enrichment_parts = [base_prompt]
        
        for i, question in enumerate(request.questions):
            if str(i) in responses and responses[str(i)].strip():
                enrichment_parts.append(f"Clarification: {question}")
                enrichment_parts.append(f"Answer: {responses[str(i)]}")
        
        return "\n".join(enrichment_parts)

    async def process_conversational_message(
        self,
        project_id: str,
        user_id: str,
        message_content: str,
        thread_id: str,
        conversation_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process a conversational message that doesn't require code generation.
        
        This handles follow-up questions, modifications, discussions, etc.
        """
        try:
            conversation_key = f"{thread_id}_{user_id}"
            
            # Update conversation tracking
            if conversation_key not in self.active_conversations:
                self.active_conversations[conversation_key] = {
                    "thread_id": thread_id,
                    "user_id": user_id,
                    "project_id": project_id,
                    "conversation_history": [],
                    "last_activity": datetime.utcnow(),
                    "mode": "conversational"
                }
            
            conversation = self.active_conversations[conversation_key]
            
            # Add message to history
            conversation["conversation_history"].append({
                "role": "user",
                "content": message_content,
                "timestamp": datetime.utcnow()
            })
            
            # Send typing indicator
            await websocket_manager.send_to_user(user_id, {
                "type": "bot_typing",
                "thread_id": thread_id,
                "message": "Thinking...",
                "timestamp": datetime.utcnow().isoformat()
            })
            
            # Generate conversational response
            response = await self._generate_conversational_response(
                message_content, 
                conversation["conversation_history"],
                conversation_context
            )
            
            # Add bot response to history
            conversation["conversation_history"].append({
                "role": "assistant",
                "content": response["content"],
                "timestamp": datetime.utcnow(),
                "response_type": response["type"]
            })
            
            conversation["last_activity"] = datetime.utcnow()
            
            # Send response via WebSocket
            await websocket_manager.send_to_user(user_id, {
                "type": "conversational_response",
                "thread_id": thread_id,
                "content": response["content"],
                "response_type": response["type"],
                "suggestions": response.get("suggestions", []),
                "can_generate_code": response.get("can_generate_code", False),
                "timestamp": datetime.utcnow().isoformat()
            })
            
            return {
                "thread_id": thread_id,
                "status": "conversational_response",
                "response": response,
                "next_action": "continue_conversation"
            }
            
        except Exception as e:
            logger.error(f"Error processing conversational message: {e}")
            await self._notify_error(user_id, thread_id, str(e))
            raise AutonomousChatServiceError(f"Conversational processing failed: {e}")

    async def _generate_conversational_response(
        self,
        message: str,
        conversation_history: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate a conversational response using LLM.
        
        This can handle various types of conversations:
        - Questions about infrastructure
        - Explanations of generated code
        - Modifications to existing code
        - General infrastructure discussions
        """
        try:
            from app.services.code_generation.llm_providers.base import LLMConfig, LLMRequest
            
            # Build conversation context
            history_text = ""
            for msg in conversation_history[-10:]:  # Last 10 messages for context
                role = "User" if msg["role"] == "user" else "Assistant"
                history_text += f"{role}: {msg['content']}\n"
            
            # Determine response type and generate appropriate prompt
            response_type = self._classify_message_intent(message, conversation_history)
            
            if response_type == "code_explanation":
                prompt = self._build_code_explanation_prompt(message, history_text, context)
            elif response_type == "code_modification":
                prompt = self._build_code_modification_prompt(message, history_text, context)
            elif response_type == "infrastructure_question":
                prompt = self._build_infrastructure_qa_prompt(message, history_text, context)
            elif response_type == "general_discussion":
                prompt = self._build_general_discussion_prompt(message, history_text, context)
            else:
                prompt = self._build_default_conversation_prompt(message, history_text, context)
            
            # Generate response using LLM
            config = LLMConfig(
                api_key=settings.LLM_API_KEY,
                model="claude-3-sonnet-20240229",
                max_tokens=1000,
                temperature=0.7
            )
            
            provider = self.provider_factory.create_provider("claude", config)
            
            request = LLMRequest(
                prompt=prompt,
                config=config,
                system_message="You are a helpful infrastructure and cloud architecture assistant. Provide clear, accurate, and actionable responses."
            )
            
            llm_response = await provider.generate_response(request)
            
            # Parse response and add suggestions
            response_content = llm_response.content.strip()
            suggestions = self._generate_conversation_suggestions(response_type, message, context)
            
            return {
                "content": response_content,
                "type": response_type,
                "suggestions": suggestions,
                "can_generate_code": self._can_generate_code_from_context(message, conversation_history),
                "confidence": 0.8  # Could be calculated based on LLM response
            }
            
        except Exception as e:
            logger.error(f"Error generating conversational response: {e}")
            return {
                "content": "I apologize, but I encountered an error while processing your message. Could you please try rephrasing your question?",
                "type": "error",
                "suggestions": ["Try asking a different question", "Start a new conversation"],
                "can_generate_code": False
            }

    def _classify_message_intent(
        self, 
        message: str, 
        history: List[Dict[str, Any]]
    ) -> str:
        """Classify the intent of a conversational message."""
        message_lower = message.lower()
        
        # Check for code explanation requests
        if any(keyword in message_lower for keyword in [
            "explain", "what does", "how does", "why", "what is", "tell me about"
        ]):
            return "code_explanation"
        
        # Check for modification requests
        if any(keyword in message_lower for keyword in [
            "change", "modify", "update", "add", "remove", "replace", "different"
        ]):
            return "code_modification"
        
        # Check for infrastructure questions
        if any(keyword in message_lower for keyword in [
            "best practice", "recommend", "should i", "which", "better", "security", "performance"
        ]):
            return "infrastructure_question"
        
        # Check for generation requests
        if any(keyword in message_lower for keyword in [
            "create", "generate", "build", "set up", "deploy", "provision"
        ]):
            return "generation_request"
        
        return "general_discussion"

    def _build_code_explanation_prompt(
        self, 
        message: str, 
        history: str, 
        context: Optional[Dict[str, Any]]
    ) -> str:
        """Build prompt for code explanation requests."""
        return f"""You are explaining infrastructure code and concepts to a user.

Conversation History:
{history}

Current Question: {message}

Context: {json.dumps(context, indent=2) if context else "No additional context"}

Please provide a clear, detailed explanation that:
1. Answers the user's specific question
2. Explains the technical concepts involved
3. Provides practical examples if helpful
4. Suggests related topics they might want to explore

Keep your response conversational and educational."""

    def _build_code_modification_prompt(
        self, 
        message: str, 
        history: str, 
        context: Optional[Dict[str, Any]]
    ) -> str:
        """Build prompt for code modification requests."""
        return f"""You are helping a user modify or improve their infrastructure code.

Conversation History:
{history}

Modification Request: {message}

Context: {json.dumps(context, indent=2) if context else "No additional context"}

Please provide:
1. A clear explanation of what changes are needed
2. The reasoning behind the modifications
3. Any potential impacts or considerations
4. Step-by-step guidance if applicable

If the user wants to generate new code with these modifications, let them know they can ask you to "generate updated code" or similar."""

    def _build_infrastructure_qa_prompt(
        self, 
        message: str, 
        history: str, 
        context: Optional[Dict[str, Any]]
    ) -> str:
        """Build prompt for infrastructure Q&A."""
        return f"""You are answering questions about cloud infrastructure, best practices, and architecture.

Conversation History:
{history}

Question: {message}

Context: {json.dumps(context, indent=2) if context else "No additional context"}

Please provide:
1. A comprehensive answer to their question
2. Best practices and recommendations
3. Potential alternatives or considerations
4. Real-world examples when helpful

Focus on practical, actionable advice."""

    def _build_general_discussion_prompt(
        self, 
        message: str, 
        history: str, 
        context: Optional[Dict[str, Any]]
    ) -> str:
        """Build prompt for general infrastructure discussions."""
        return f"""You are having a friendly, informative conversation about infrastructure and cloud technologies.

Conversation History:
{history}

User Message: {message}

Context: {json.dumps(context, indent=2) if context else "No additional context"}

Please respond in a conversational, helpful manner. Share insights, ask clarifying questions if needed, and guide the conversation toward actionable outcomes when appropriate."""

    def _build_default_conversation_prompt(
        self, 
        message: str, 
        history: str, 
        context: Optional[Dict[str, Any]]
    ) -> str:
        """Build default conversation prompt."""
        return f"""You are a helpful infrastructure assistant having a conversation with a user.

Conversation History:
{history}

User Message: {message}

Please respond helpfully and conversationally. If the user seems to want to generate infrastructure code, guide them toward that. If they have questions, answer them clearly."""

    def _generate_conversation_suggestions(
        self, 
        response_type: str, 
        message: str, 
        context: Optional[Dict[str, Any]]
    ) -> List[str]:
        """Generate conversation suggestions based on response type."""
        suggestions = []
        
        if response_type == "code_explanation":
            suggestions = [
                "Can you show me an example?",
                "What are the best practices for this?",
                "How would I modify this for production?",
                "Generate code with these concepts"
            ]
        elif response_type == "code_modification":
            suggestions = [
                "Generate the updated code",
                "What other improvements could I make?",
                "Show me the differences",
                "Explain the security implications"
            ]
        elif response_type == "infrastructure_question":
            suggestions = [
                "Can you create an example for me?",
                "What would this look like in Terraform?",
                "Compare this with alternatives",
                "Show me a complete implementation"
            ]
        else:
            suggestions = [
                "Can you help me create this?",
                "Tell me more about best practices",
                "What should I consider for production?",
                "Generate some example code"
            ]
        
        return suggestions[:3]  # Limit to 3 suggestions

    def _can_generate_code_from_context(
        self, 
        message: str, 
        history: List[Dict[str, Any]]
    ) -> bool:
        """Determine if code generation is possible from current context."""
        message_lower = message.lower()
        
        # Direct generation requests
        if any(keyword in message_lower for keyword in [
            "generate", "create", "build", "show me code", "write", "implement"
        ]):
            return True
        
        # Check if there's enough context from conversation
        infrastructure_mentions = 0
        for msg in history[-5:]:  # Check last 5 messages
            content_lower = msg["content"].lower()
            if any(keyword in content_lower for keyword in [
                "aws", "azure", "gcp", "terraform", "cloudformation", 
                "s3", "ec2", "vpc", "lambda", "kubernetes", "docker"
            ]):
                infrastructure_mentions += 1
        
        return infrastructure_mentions >= 2

    async def _generate_questions_with_prompt(self, enhanced_prompt: str) -> List[str]:
        """Generate questions using a custom prompt."""
        try:
            from app.services.code_generation.llm_providers.base import LLMConfig, LLMRequest
            
            config = LLMConfig(
                api_key=settings.LLM_API_KEY,
                model="claude-3-haiku-20240307",
                temperature=0.3,
                max_tokens=500,
                timeout=30
            )
            
            provider = self.provider_factory.create_provider("claude", config)
            
            request = LLMRequest(
                prompt=enhanced_prompt,
                config=config,
                system_message="Generate specific, actionable questions for infrastructure code generation."
            )
            
            response = await provider.generate(request)
            return self._parse_question_response(response.content)
            
        except Exception as e:
            logger.error(f"Error generating questions with custom prompt: {e}")
            return []

    def cleanup_conversation(self, conversation_key: str) -> None:
        """Clean up conversation tracking."""
        if conversation_key in self.active_conversations:
            del self.active_conversations[conversation_key]