import React from 'react';
import { InfrastructureChatbot } from '@/components/chat/InfrastructureChatbot';

const ChatDemo: React.FC = () => {
    return (
        <div className="h-screen flex flex-col">
            <InfrastructureChatbot />
        </div>
    );
};

export default ChatDemo;