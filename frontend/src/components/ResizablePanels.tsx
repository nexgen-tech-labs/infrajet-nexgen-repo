import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import { GripVertical } from "lucide-react";

interface ResizablePanelsProps {
    leftPanel: React.ReactNode;
    rightPanel: React.ReactNode;
    defaultSizes?: [number, number];
    minSizes?: [number, number];
    collapsedRight?: boolean;
}

const ResizablePanels = ({
    leftPanel,
    rightPanel,
    defaultSizes = [50, 50],
    minSizes = [30, 30],
    collapsedRight = false
}: ResizablePanelsProps) => {
    if (collapsedRight) {
        return (
            <div className="flex h-full transition-all duration-300 ease-in-out">
                <div className="flex-1 transition-all duration-300 ease-in-out">
                    {leftPanel}
                </div>
                <div className="w-10 border-l border-border/50 transition-all duration-300 ease-in-out">
                    {rightPanel}
                </div>
            </div>
        );
    }

    return (
        <PanelGroup direction="horizontal" className="h-full">
            <Panel defaultSize={defaultSizes[0]} minSize={minSizes[0]}>
                {leftPanel}
            </Panel>

            <PanelResizeHandle className="w-2 bg-border hover:bg-primary/20 transition-colors flex items-center justify-center group">
                <GripVertical className="w-3 h-3 text-muted-foreground group-hover:text-primary transition-colors" />
            </PanelResizeHandle>

            <Panel defaultSize={defaultSizes[1]} minSize={minSizes[1]}>
                {rightPanel}
            </Panel>
        </PanelGroup>
    );
};

export default ResizablePanels;