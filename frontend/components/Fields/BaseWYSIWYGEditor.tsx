import { useCallback, useEffect, useRef, useState } from 'react';

import Document from '@tiptap/extension-document'
import Dropcursor from '@tiptap/extension-dropcursor'
import Paragraph from '@tiptap/extension-paragraph'
import HorizontalRule from '@tiptap/extension-horizontal-rule'
import Text from '@tiptap/extension-text'
import Table from '@tiptap/extension-table'
import TableCell from '@tiptap/extension-table-cell'
import TableHeader from '@tiptap/extension-table-header'
import TableRow from '@tiptap/extension-table-row'
import Bold from '@tiptap/extension-bold'
import Italic from '@tiptap/extension-italic'
import Underline from '@tiptap/extension-underline'
import Strike from '@tiptap/extension-strike'
import Code from '@tiptap/extension-code'
import CodeBlock from '@tiptap/extension-code-block'
import Highlight from '@tiptap/extension-highlight'
import Link from '@tiptap/extension-link'
import TextStyle from '@tiptap/extension-text-style'
import History from '@tiptap/extension-history'
import HardBreak from '@tiptap/extension-hard-break'
import Blockquote from '@tiptap/extension-blockquote'
import Image from "@tiptap/extension-image";
import { mergeAttributes } from "@tiptap/core";
import { EditorContent, useEditor } from '@tiptap/react'
import { useQuery } from '@tanstack/react-query';

import CrudKitAPIClient from "../../data/api";

const StyledImage = Image.extend({
  name: "image",

  addAttributes() {
    return {
      ...this.parent?.(),
      baseStyle: {
        default: "",
        rendered: false,
        parseHTML: (element) => element.getAttribute("style"),
      },
    };
  },

  renderHTML({ node, HTMLAttributes }) {
    const baseStyle = node.attrs.baseStyle || "";
    const style = HTMLAttributes.style || "";
    if (style || baseStyle) {
      HTMLAttributes.style = mergeStyles(baseStyle, style);
    }
    return [
      "img",
      mergeAttributes(this.options.HTMLAttributes, HTMLAttributes),
    ];
  },
});

function mergeStyles(...styleStrings) {
  const styleObject = {};
  for (const styleString of styleStrings) {
    const styleArray = styleString
      .split(";")
      .map((s) => s.trim())
      .filter(Boolean);

    for (const style of styleArray) {
      const [property, value] = style.split(":");
      styleObject[property.trim()] = value.trim();
    }
  }

  const finalStyleString = Object.entries(styleObject)
    .map(([property, value]) => `${property}: ${value}`)
    .join("; ");

  return finalStyleString;
}

const MenuButton = ({
  onClick,
  isActive = false,
  disabled = false,
  title,
  children
}) => (
  <button
    type="button"
    onClick={onClick}
    className={`p-1.5 rounded ${
      isActive
        ? 'bg-bg-4 text-fg-1'
        : 'text-fg-2 hover:bg-bg-3 hover:text-fg-1'
    } ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
    disabled={disabled}
    title={title}
  >
    {children}
  </button>
);

function SnippetPicker({ editor, modelType }) {
  const [search, setSearch] = useState('');
  const panelRef = useRef<HTMLDivElement>(null);

  const { data: snippetsData } = useQuery({
    queryKey: ['snippets'],
    queryFn: () => new CrudKitAPIClient().list("SNP"),
    staleTime: 60000,
  });

  const allSnippets = snippetsData?.isPaginated ? snippetsData.results : (snippetsData || []);

  const filteredSnippets = allSnippets.filter(s => {
    const matchesModel = !s.model_types?.length || !modelType || s.model_types.includes(modelType);
    const matchesSearch = !search || s.name.toLowerCase().includes(search.toLowerCase());
    return matchesModel && matchesSearch;
  });

  const insertSnippet = (snippet) => {
    editor.chain().focus().insertContent(snippet.body).run();
  };

  return (
    <div ref={panelRef} className="p-2 bg-bg-2 border-x border-t border-border-1">
      <input
        type="text"
        placeholder="Search snippets..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="w-full p-1 border border-border-1 rounded text-sm mb-2"
        autoFocus
      />
      <div className="max-h-[200px] overflow-y-auto">
        {filteredSnippets.length === 0 ? (
          <p className="text-sm text-fg-3 p-1">No snippets found</p>
        ) : (
          filteredSnippets.map((snippet) => (
            <button
              key={snippet.id}
              type="button"
              onClick={() => insertSnippet(snippet)}
              className="block w-full text-left px-2 py-1 text-sm rounded hover:bg-bg-3 hover:text-primary-300"
            >
              {snippet.name}
            </button>
          ))
        )}
      </div>
    </div>
  );
}

interface BaseWYSIWYGEditorProps {
  value: string;
  onChange: (html: string) => void;
  onBlur: () => void;
  hasError: boolean;
  maxHeight?: string;
  modelType?: string;
}

export default function BaseWYSIWYGEditor({
  value,
  onChange,
  onBlur,
  hasError,
  maxHeight,
  modelType,
}: BaseWYSIWYGEditorProps) {
  const [linkUrl, setLinkUrl] = useState('');
  const [showLinkModal, setShowLinkModal] = useState(false);
  const [showSnippets, setShowSnippets] = useState(false);

  const editorClass = `ck-tiptap-editor max-w-none border ${hasError ? 'border-danger' : 'border-border-1'} rounded-b-md p-4 min-h-[200px]${maxHeight ? ` max-h-[${maxHeight}] overflow-y-auto` : ''} focus:outline-none focus:ring-0 focus:border-primary-400 bg-bg-2 text-fg-1`;

  const editor = useEditor({
    editorProps: {
      attributes: {
        class: editorClass,
      },
    },
    extensions: [
      Document,
      Paragraph,
      Text,
      StyledImage.configure({
        inline: true,
        allowBase64: true,
      }),
      Dropcursor,
      HorizontalRule,
      Table.configure({
        resizable: true,
        HTMLAttributes: {
          class: 'w-full border-collapse border border-border-1',
        },
      }),
      Blockquote.configure({
        HTMLAttributes: {
          class: 'pl-4 italic',
          style: 'border-left: 4px solid var(--primary-400);',
        },
      }),
      TableCell.configure({
        HTMLAttributes: {
          class: 'border border-border-1 p-2',
        },
      }),
      TableHeader.configure({
        HTMLAttributes: {
          class: 'border border-border-1 p-2 bg-bg-3 font-bold',
        },
      }),
      TableRow,
      Bold,
      Italic,
      Underline,
      Strike,
      Code.configure({
        HTMLAttributes: {
          class: 'bg-bg-3 rounded px-1 font-mono',
        },
      }),
      CodeBlock.configure({
        HTMLAttributes: {
          class: 'bg-bg-3 rounded p-2 font-mono',
        },
      }),
      Highlight.configure({
        HTMLAttributes: {
          style: 'background: color-mix(in oklab, var(--warn) 30%, transparent);',
        },
      }),
      Link.configure({
        openOnClick: false,
        HTMLAttributes: {
          class: 'underline',
          style: 'color: var(--primary-300);',
        },
      }),
      TextStyle,
      History,
      HardBreak
    ],
    content: value || "",
    onUpdate({ editor }) {
      onChange(editor.getHTML());
    },
    onBlur() {
      onBlur();
    }
  });

  useEffect(() => {
    if (editor && value !== editor.getHTML()) {
      editor.commands.setContent(value || "");
    }
  }, [editor, value]);

  const setLink = useCallback(() => {
    if (!editor) return;

    if (!linkUrl) {
      editor.chain().focus().extendMarkRange('link').unsetLink().run();
      return;
    }

    editor.chain()
      .focus()
      .extendMarkRange('link')
      .setLink({ href: linkUrl })
      .run();

    setShowLinkModal(false);
    setLinkUrl('');
  }, [editor, linkUrl]);

  const addImage = useCallback(() => {
    if (!editor) return;

    const url = window.prompt('Enter image URL');

    if (url) {
      editor.chain().focus().setImage({ src: url }).run();
    }
  }, [editor]);

  const addTable = useCallback(() => {
    if (!editor) return;

    editor.chain()
      .focus()
      .insertTable({ rows: 3, cols: 3, withHeaderRow: true })
      .run();
  }, [editor]);

  if (!editor) {
    return null;
  }

  return (
    <div className="w-full">
      {/* Editor Toolbar */}
      <div className="flex flex-wrap items-center gap-1 p-2 bg-bg-2 border border-border-1 border-b-0 rounded-t-md">
        {/* Text Formatting */}
        <MenuButton
          onClick={() => editor.chain().focus().toggleBold().run()}
          isActive={editor.isActive('bold')}
          title="Bold"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
            <path d="M8 11h4.5a2.5 2.5 0 0 0 0-5H8v5Zm10 4.5a4.5 4.5 0 0 1-4.5 4.5H6V4h6.5a4.5 4.5 0 0 1 3.256 7.613A4.5 4.5 0 0 1 18 15.5ZM8 13v5h5.5a2.5 2.5 0 0 0 0-5H8Z"/>
          </svg>
        </MenuButton>

        <MenuButton
          onClick={() => editor.chain().focus().toggleItalic().run()}
          isActive={editor.isActive('italic')}
          title="Italic"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
            <path d="M15 20H7v-2h2.927l2.116-12H9V4h8v2h-2.927l-2.116 12H15v2Z"/>
          </svg>
        </MenuButton>

        <MenuButton
          onClick={() => editor.chain().focus().toggleUnderline().run()}
          isActive={editor.isActive('underline')}
          title="Underline"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
            <path d="M8 3v9a4 4 0 0 0 8 0V3h2v9a6 6 0 0 1-12 0V3h2ZM4 20h16v2H4v-2Z"/>
          </svg>
        </MenuButton>

        <MenuButton
          onClick={() => editor.chain().focus().toggleStrike().run()}
          isActive={editor.isActive('strike')}
          title="Strikethrough"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
            <path d="M17.154 14c.23.516.346 1.09.346 1.72 0 1.342-.524 2.392-1.571 3.147C14.88 19.622 13.433 20 11.586 20c-1.64 0-3.263-.381-4.87-1.144V16.6c1.52.877 3.075 1.316 4.666 1.316 2.551 0 3.83-.732 3.839-2.197a2.21 2.21 0 0 0-.648-1.603l-.12-.117H3v-2h18v2h-3.846zm-4.078-3H7.629a4.086 4.086 0 0 1-.481-.522C6.716 9.92 6.5 9.246 6.5 8.452c0-1.236.466-2.287 1.397-3.153C8.83 4.433 10.271 4 12.222 4c1.471 0 2.879.328 4.222.984v2.152c-1.2-.687-2.515-1.03-3.946-1.03-2.48 0-3.719.782-3.719 2.346 0 .42.218.786.654 1.099.436.313.974.562 1.613.75.62.18 1.297.414 2.03.699z"/>
          </svg>
        </MenuButton>

        <div className="h-6 mx-1 border-l border-border-1"></div>

        {/* Link */}
        <MenuButton
          onClick={() => {
            if (editor.isActive('link')) {
              editor.chain().focus().unsetLink().run();
            } else {
              setShowLinkModal(true);
              setShowSnippets(false);
            }
          }}
          isActive={editor.isActive('link')}
          title="Link"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
            <path d="M18.364 15.536 16.95 14.12l1.414-1.414a5 5 0 1 0-7.071-7.071L9.879 7.05 8.464 5.636 9.88 4.222a7 7 0 0 1 9.9 9.9l-1.415 1.414zm-2.828 2.828-1.415 1.414a7 7 0 0 1-9.9-9.9l1.415-1.414L7.05 9.88l-1.414 1.414a5 5 0 1 0 7.071 7.071l1.414-1.414 1.415 1.414zm-.708-10.607 1.415 1.415-7.071 7.07-1.415-1.414 7.071-7.07z"/>
          </svg>
        </MenuButton>

        {/* Image */}
        <MenuButton
          onClick={addImage}
          title="Insert Image"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
            <path d="M5 11.1l2-2 5.5 5.5 3.5-3.5 3 3V5H5v6.1zm0 2.829V19h3.1l2.55-2.55-2.55-2.55-3.1 3.1zm7.85 2.55L16.9 19H19v-2.1l-3.15-3.15-3 3.15zM4 3h16a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1zm6 8a2 2 0 1 1 0-4 2 2 0 0 1 0 4z"/>
          </svg>
        </MenuButton>

        {/* Table */}
        <MenuButton
          onClick={addTable}
          disabled={editor.isActive('table')}
          title="Insert Table"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
            <path d="M4 8h16V5H4v3zm10 11v-9h-4v9h4zm2 0h4v-9h-4v9zm-8 0v-9H4v9h4zM3 3h18a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z"/>
          </svg>
        </MenuButton>

        <div className="h-6 mx-1 border-l border-border-1"></div>

        {/* Block Formatting */}
        <MenuButton
          onClick={() => editor.chain().focus().toggleBlockquote().run()}
          isActive={editor.isActive('blockquote')}
          title="Blockquote"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
            <path d="M4.583 17.321C3.553 16.227 3 15 3 13.011c0-3.5 2.457-6.637 6.03-8.188l.893 1.378c-3.335 1.804-3.987 4.145-4.247 5.621.537-.278 1.24-.375 1.929-.311 1.804.167 3.226 1.648 3.226 3.489a3.5 3.5 0 0 1-3.5 3.5c-1.073 0-2.099-.49-2.748-1.179zm10 0C13.553 16.227 13 15 13 13.011c0-3.5 2.457-6.637 6.03-8.188l.893 1.378c-3.335 1.804-3.987 4.145-4.247 5.621.537-.278 1.24-.375 1.929-.311 1.804.167 3.226 1.648 3.226 3.489a3.5 3.5 0 0 1-3.5 3.5c-1.073 0-2.099-.49-2.748-1.179z"/>
          </svg>
        </MenuButton>

        <MenuButton
          onClick={() => editor.chain().focus().toggleCodeBlock().run()}
          isActive={editor.isActive('codeBlock')}
          title="Code Block"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
            <path d="M3 3h18a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1zm1 2v14h16V5H4zm16 7l-3.535 3.536-1.415-1.415L17.172 12l-2.122-2.121 1.415-1.415L20 12zM6.828 12l2.122 2.121-1.415 1.415L4 12l3.535-3.536 1.415 1.415L6.828 12z"/>
          </svg>
        </MenuButton>

        <MenuButton
          onClick={() => editor.chain().focus().setHorizontalRule().run()}
          title="Horizontal Rule"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
            <path d="M2 11h2v2H2z"/><path d="M6 11h2v2H6z"/><path d="M10 11h2v2h-2z"/><path d="M14 11h2v2h-2z"/><path d="M18 11h2v2h-2z"/><path d="M21 11h2v2h-2z"/>
          </svg>
        </MenuButton>

        <div className="h-6 mx-1 border-l border-border-1"></div>

        {/* Snippet */}
        <MenuButton
          onClick={() => {
            setShowSnippets(!showSnippets);
            setShowLinkModal(false);
          }}
          isActive={showSnippets}
          title="Insert Snippet"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
            <path d="M20 22H4a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1h16a1 1 0 0 1 1 1v18a1 1 0 0 1-1 1zM5 20h14V4H5v16zm2-6h10v2H7v-2zm0-4h10v2H7V10zm0-4h10v2H7V6z"/>
          </svg>
        </MenuButton>
      </div>

      {/* Link Modal */}
      {showLinkModal && (
        <div className="p-2 bg-bg-2 border-x border-t border-border-1">
          <div className="flex items-center gap-2">
            <input
              type="text"
              placeholder="Enter URL"
              value={linkUrl}
              onChange={(e) => setLinkUrl(e.target.value)}
              className="flex-1 p-1 border border-border-1 rounded text-sm"
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  setLink();
                }
              }}
            />
            <button
              onClick={setLink}
              className="px-2 py-1 bg-primary-400 text-bg-1 rounded text-sm"
            >
              Apply
            </button>
            <button
              onClick={() => setShowLinkModal(false)}
              className="px-2 py-1 bg-bg-3 text-fg-1 rounded text-sm"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Snippet Picker */}
      {showSnippets && (
        <SnippetPicker
          editor={editor}
          modelType={modelType}
        />
      )}

      {/* Editor Content */}
      <EditorContent editor={editor} />
    </div>
  );
}
