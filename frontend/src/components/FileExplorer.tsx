import { useState } from "react";
import { ChevronRight, ChevronDown, ChevronLeft, File, Folder, FolderOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";

interface FileNode {
    name: string;
    type: 'file' | 'folder';
    path: string;
    children?: FileNode[];
    content?: string;
}

interface FileExplorerProps {
    files: FileNode[];
    onFileSelect: (file: FileNode) => void;
    selectedFile?: FileNode;
    isCollapsed?: boolean;
    onToggleCollapse?: () => void;
}

const FileExplorer = ({ files, onFileSelect, selectedFile, isCollapsed = false, onToggleCollapse }: FileExplorerProps) => {
    const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set(['infrastructure', 'modules', 'modules/ec2']));

    const toggleFolder = (path: string) => {
        const newExpanded = new Set(expandedFolders);
        if (newExpanded.has(path)) {
            newExpanded.delete(path);
        } else {
            newExpanded.add(path);
        }
        setExpandedFolders(newExpanded);
    };

    const renderNode = (node: FileNode, depth = 0) => {
        const isExpanded = expandedFolders.has(node.path);
        const isSelected = selectedFile?.path === node.path;

        return (
            <div key={node.path}>
                <Button
                    variant="ghost"
                    className={`w-full justify-start h-9 px-2 rounded-lg transition-all duration-200 ${isSelected
                        ? 'bg-gradient-to-r from-primary/20 to-primary/10 text-primary border border-primary/20 shadow-sm'
                        : 'hover:bg-muted/50 hover:shadow-sm'
                        }`}
                    style={{ paddingLeft: `${depth * 16 + 8}px` }}
                    onClick={() => {
                        if (node.type === 'folder') {
                            toggleFolder(node.path);
                        } else {
                            onFileSelect(node);
                        }
                    }}
                >
                    <div className="flex items-center gap-2 text-sm">
                        {node.type === 'folder' ? (
                            <>
                                {isExpanded ? (
                                    <ChevronDown className="w-4 h-4 text-muted-foreground" />
                                ) : (
                                    <ChevronRight className="w-4 h-4 text-muted-foreground" />
                                )}
                                {isExpanded ? (
                                    <FolderOpen className="w-4 h-4 text-blue-500" />
                                ) : (
                                    <Folder className="w-4 h-4 text-blue-500" />
                                )}
                            </>
                        ) : (
                            <>
                                <div className="w-4" />
                                <File className={`w-4 h-4 ${node.name.endsWith('.tf') ? 'text-purple-500' :
                                    node.name.endsWith('.yaml') || node.name.endsWith('.yml') ? 'text-orange-500' :
                                        node.name.endsWith('.md') ? 'text-blue-500' :
                                            node.name.endsWith('.json') ? 'text-yellow-500' :
                                                'text-muted-foreground'
                                    }`} />
                            </>
                        )}
                        <span className={`truncate ${isSelected ? 'font-medium' : ''}`}>{node.name}</span>
                    </div>
                </Button>

                {node.type === 'folder' && isExpanded && node.children && (
                    <div>
                        {node.children.map(child => renderNode(child, depth + 1))}
                    </div>
                )}
            </div>
        );
    };

    return (
        <div className="h-full border-r border-border/50">
            <div className={`border-b border-border/50 bg-gradient-to-r from-muted/30 to-muted/10 ${isCollapsed ? 'p-2 flex flex-col items-center justify-center h-full' : 'p-4'}`}>
                <div className={`flex items-center gap-2 ${isCollapsed ? 'flex-col gap-1' : ''}`}>
                    <div className="p-1.5 rounded-lg bg-primary/10">
                        <FolderOpen className="w-4 h-4 text-primary" />
                    </div>
                    <h3 className={`font-semibold text-foreground ${isCollapsed ? 'text-xs' : ''}`} style={isCollapsed ? { writingMode: 'vertical-rl', textOrientation: 'mixed' } : {}}>Files</h3>
                    {onToggleCollapse && (
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={onToggleCollapse}
                            className={`h-6 w-6 p-0 ${isCollapsed ? 'self-center' : ''}`}
                        >
                            {isCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
                        </Button>
                    )}
                </div>
                {!isCollapsed && <p className="text-xs text-muted-foreground mt-1">Project files and structure</p>}
            </div>
            {!isCollapsed && (
                <ScrollArea className="h-[calc(100%-72px)]">
                    <div className="p-3 space-y-1">
                        {files.map(node => renderNode(node))}
                    </div>
                </ScrollArea>
            )}
        </div>
    );
};

export default FileExplorer;