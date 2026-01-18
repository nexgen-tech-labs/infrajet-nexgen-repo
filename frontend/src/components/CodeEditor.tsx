import { Editor } from '@monaco-editor/react';

interface CodeEditorProps {
    value: string;
    language: string;
    onChange?: (value: string | undefined) => void;
    readOnly?: boolean;
    height?: string;
    onEditorMount?: (editor: any) => void;
}

const CodeEditor = ({
    value,
    language,
    onChange,
    readOnly = false,
    height = "100%",
    onEditorMount
}: CodeEditorProps) => {

    const getLanguage = (lang: string) => {
        switch (lang.toLowerCase()) {
            case 'terraform':
            case 'hcl':
                return 'hcl';
            case 'yaml':
            case 'yml':
                return 'yaml';
            case 'json':
                return 'json';
            case 'javascript':
            case 'js':
                return 'javascript';
            case 'typescript':
            case 'ts':
                return 'typescript';
            case 'python':
            case 'py':
                return 'python';
            case 'dockerfile':
                return 'dockerfile';
            case 'shell':
            case 'bash':
                return 'shell';
            default:
                return 'plaintext';
        }
    };

    return (
        <Editor
            height={height}
            language={getLanguage(language)}
            value={value}
            onChange={onChange}
            theme="vs-dark"
            onMount={onEditorMount}
            options={{
                readOnly,
                minimap: { enabled: false },
                fontSize: 14,
                lineNumbers: 'on',
                roundedSelection: false,
                scrollBeyondLastLine: false,
                automaticLayout: true,
                tabSize: 2,
                insertSpaces: true,
                wordWrap: 'on',
                folding: true,
                lineDecorationsWidth: 10,
                lineNumbersMinChars: 3,
                glyphMargin: false,
                find: {
                    addExtraSpaceOnTop: false,
                    autoFindInSelection: 'never',
                    seedSearchStringFromSelection: 'always'
                },
                scrollbar: {
                    vertical: 'auto',
                    horizontal: 'auto',
                    useShadows: false,
                    verticalHasArrows: false,
                    horizontalHasArrows: false,
                },
            }}
        />
    );
};

export default CodeEditor;