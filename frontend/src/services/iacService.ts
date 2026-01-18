
import { supabase } from "@/integrations/supabase/client";

export interface GenerateIaCRequest {
  prompt: string;
  provider: string;
  conversationHistory?: any[];
  signal?: AbortSignal;
}

export interface GenerateIaCResponse {
  generatedCode: string;
  provider: string;
  usage?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
}

export const generateIaCCode = async (request: GenerateIaCRequest): Promise<GenerateIaCResponse> => {
  const { signal, ...body } = request;
  const { data, error } = await supabase.functions.invoke('generate-iac-code', {
    body,
    ...(signal && { signal })
  });

  if (error) {
    console.error('Error calling generate-iac-code function:', error);
    throw new Error(`Failed to generate code: ${error.message}`);
  }

  if (data.error) {
    throw new Error(data.error);
  }

  return data;
};
