import React from 'react';
import Header from '@/components/Header';
import Footer from '@/components/Footer';
import ProjectManagement from './ProjectManagement';

export const Projects: React.FC = () => {
    return (
        <div className="min-h-screen bg-background">
            <Header />
            <main className="flex-1">
                <ProjectManagement />
            </main>
            <Footer />
        </div>
    );
};