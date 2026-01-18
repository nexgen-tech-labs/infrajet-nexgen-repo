import { useState, useCallback } from 'react';
import { getAuthToken } from '@/services/infrajetApi';

const API_BASE_URL = window.__RUNTIME_CONFIG__?.INFRAJET_API_URL;

export interface Generation {
  generation_id: string;
  query: string;
  scenario: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'COMPLETED';
  created_at: string;
  updated_at: string;
  generation_hash: string;
  error_message: string | null;
  files: GenerationFile[];
  file_count: number;
  description?: string;
  summary?: string;
}

export interface GenerationFile {
  name: string;
  path: string;
  size: number;
  modified_date: string;
  content_type: string;
  content?: string;
}

export interface GenerationsResponse {
  project_id: string;
  generations: Generation[];
  total_count: number;
  message: string;
}

export interface Generation {
  generation_id: string;
  query: string;
  scenario: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'COMPLETED';
  created_at: string;
  updated_at: string;
  generation_hash: string;
  error_message: string | null;
  files: GenerationFile[];
  file_count: number;
  description?: string;
  summary?: string;
}

export interface GenerationFilesResponse {
  project_id: string;
  generation_id: string;
  files: GenerationFile[];
  file_count: number;
  total_size: number;
  message: string;
}

export interface GenerationFileResponse {
  project_id: string;
  generation_id: string;
  file_path: string;
  content: string;
  size: number;
  modified_date: string;
  content_type: string;
  message: string;
}

export const useProjectFiles = (projectId: string) => {
  const [generations, setGenerations] = useState<Generation[]>([]);
  const [selectedGeneration, setSelectedGeneration] = useState<Generation | null>(null);
  const [selectedFile, setSelectedFile] = useState<GenerationFile | null>(null);
  const [fileContent, setFileContent] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [loadingContent, setLoadingContent] = useState(false);

  // Fetch all generations for the project
  const fetchGenerations = useCallback(async () => {
    try {
      setLoading(true);
      const token = await getAuthToken();

      const response = await fetch(`${API_BASE_URL}/api/v1/projects/${projectId}/generations`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        // If API doesn't exist, use mock data
        console.warn('Generations API not available, using mock data');
        setGenerations([]);
        return;
      }

      const data: GenerationsResponse = await response.json();
      setGenerations(data.generations || []);
    } catch (error) {
      console.error('Error fetching generations:', error);
      // Set empty array to prevent crashes
      setGenerations([]);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  // Fetch files for a specific generation
  const fetchGenerationFiles = useCallback(async (generationId: string, includeContent = false) => {
    try {
      setLoadingFiles(true);
      const token = await getAuthToken();

      const params = new URLSearchParams();
      if (includeContent) params.set('include_content', 'true');

      const response = await fetch(
        `${API_BASE_URL}/api/v1/projects/${projectId}/generations/${generationId}/files?${params}`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        }
      );

      if (!response.ok) {
        throw new Error(`Failed to fetch generation files: ${response.status}`);
      }

      const data: GenerationFilesResponse = await response.json();

      // Update the generation with full file details
      setGenerations(prev =>
        prev.map(gen =>
          gen.generation_id === generationId
            ? { ...gen, files: data.files }
            : gen
        )
      );

      return data.files;
    } catch (error) {
      console.error('Error fetching generation files:', error);
      return [];
    } finally {
      setLoadingFiles(false);
    }
  }, [projectId]);

  // Fetch content of a specific file
  const fetchFileContent = useCallback(async (generationId: string, filePath: string) => {
    try {
      setLoadingContent(true);
      const token = await getAuthToken();

      const response = await fetch(
        `${API_BASE_URL}/api/v1/projects/${projectId}/generations/${generationId}/files/${encodeURIComponent(filePath)}`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        }
      );

      if (!response.ok) {
        throw new Error(`Failed to fetch file content: ${response.status}`);
      }

      const data: GenerationFileResponse = await response.json();
      setFileContent(data.content);
      return data.content;
    } catch (error) {
      console.error('Error fetching file content:', error);
      return '';
    } finally {
      setLoadingContent(false);
    }
  }, [projectId]);

  // Select a generation and load its files
  const selectGeneration = useCallback(async (generation: Generation) => {
    setSelectedGeneration(generation);
    setSelectedFile(null);
    setFileContent('');

    // Load files if not already loaded
    if (!generation.files || generation.files.length === 0) {
      await fetchGenerationFiles(generation.generation_id);
    }
  }, [fetchGenerationFiles]);

  // Select a file and load its content
  const selectFile = useCallback(async (file: GenerationFile) => {
    if (!selectedGeneration) return;

    setSelectedFile(file);
    await fetchFileContent(selectedGeneration.generation_id, file.path);
  }, [selectedGeneration, fetchFileContent]);

  // Download a file
  const downloadFile = useCallback((generationId: string, filePath: string) => {
    const token = localStorage.getItem('authToken'); // Assuming token is stored locally
    const downloadUrl = `${API_BASE_URL}/api/v1/projects/${projectId}/generations/${generationId}/files/${encodeURIComponent(filePath)}/download`;

    // Create a temporary link to trigger download
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.setAttribute('download', filePath.split('/').pop() || 'file');
    link.style.display = 'none';

    // Add authorization header via fetch if needed
    fetch(downloadUrl, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    })
      .then(response => response.blob())
      .then(blob => {
        const url = window.URL.createObjectURL(blob);
        link.href = url;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);
      })
      .catch(error => {
        console.error('Download failed:', error);
      });
  }, [projectId]);

  return {
    generations,
    selectedGeneration,
    selectedFile,
    fileContent,
    loading,
    loadingFiles,
    loadingContent,
    fetchGenerations,
    fetchGenerationFiles,
    fetchFileContent,
    selectGeneration,
    selectFile,
    downloadFile
  };
};