// Input sanitization utilities for user-generated content

export interface SanitizationOptions {
  allowHtml?: boolean;
  allowCodeBlocks?: boolean;
  allowFileReferences?: boolean;
  maxLength?: number;
  allowedTags?: string[];
  allowedAttributes?: Record<string, string[]>;
}

const DEFAULT_OPTIONS: SanitizationOptions = {
  allowHtml: false,
  allowCodeBlocks: true,
  allowFileReferences: true,
  maxLength: 10000,
  allowedTags: [],
  allowedAttributes: {},
};

/**
 * Sanitizes chat message input to prevent XSS and other security issues
 */
export function sanitizeChatMessage(
  input: string,
  options: Partial<SanitizationOptions> = {}
): string {
  const opts = { ...DEFAULT_OPTIONS, ...options };

  if (!input || typeof input !== 'string') {
    return '';
  }

  let sanitized = input.trim();

  // Enforce maximum length
  if (opts.maxLength && sanitized.length > opts.maxLength) {
    sanitized = sanitized.substring(0, opts.maxLength);
  }

  // Handle code blocks first (preserve them)
  if (opts.allowCodeBlocks) {
    sanitized = preserveCodeBlocks(sanitized);
  }

  // Handle file references
  if (opts.allowFileReferences) {
    sanitized = sanitizeFileReferences(sanitized);
  }

  // HTML sanitization
  if (!opts.allowHtml) {
    sanitized = sanitizeHtml(sanitized, opts.allowedTags, opts.allowedAttributes);
  }

  // Remove null bytes and other control characters
  sanitized = removeControlCharacters(sanitized);

  // Normalize whitespace
  sanitized = normalizeWhitespace(sanitized);

  return sanitized;
}

/**
 * Preserves code blocks by temporarily replacing them with placeholders
 */
function preserveCodeBlocks(input: string): string {
  const codeBlockRegex = /```[\s\S]*?```/g;
  const inlineCodeRegex = /`[^`\n]+`/g;

  // Replace code blocks with placeholders
  const codeBlocks: string[] = [];
  let tempInput = input.replace(codeBlockRegex, (match) => {
    codeBlocks.push(match);
    return `__CODE_BLOCK_${codeBlocks.length - 1}__`;
  });

  // Replace inline code with placeholders
  const inlineCodes: string[] = [];
  tempInput = tempInput.replace(inlineCodeRegex, (match) => {
    inlineCodes.push(match);
    return `__INLINE_CODE_${inlineCodes.length - 1}__`;
  });

  // Sanitize the content outside code blocks
  tempInput = sanitizeHtml(tempInput, [], {});

  // Restore code blocks
  codeBlocks.forEach((block, index) => {
    tempInput = tempInput.replace(`__CODE_BLOCK_${index}__`, block);
  });

  // Restore inline code
  inlineCodes.forEach((code, index) => {
    tempInput = tempInput.replace(`__INLINE_CODE_${index}__`, code);
  });

  return tempInput;
}

/**
 * Sanitizes file references to prevent path traversal and other issues
 */
function sanitizeFileReferences(input: string): string {
  // Pattern for file references: @filename or file:filename
  const fileRefRegex = /(@|file:)[\w/\-\.\s]+/g;

  return input.replace(fileRefRegex, (match) => {
    const prefix = match.startsWith('@') ? '@' : 'file:';
    const filename = match.substring(prefix.length).trim();

    // Remove dangerous characters and normalize path separators
    const sanitizedFilename = filename
      .replace(/[<>:"|?*\x00-\x1f]/g, '') // Remove dangerous chars
      .replace(/\.\./g, '') // Remove directory traversal
      .replace(/\/+/g, '/') // Normalize slashes
      .replace(/\\+/g, '/') // Convert backslashes to forward slashes
      .trim();

    // Limit filename length
    const maxFilenameLength = 255;
    const truncatedFilename = sanitizedFilename.length > maxFilenameLength
      ? sanitizedFilename.substring(0, maxFilenameLength)
      : sanitizedFilename;

    return prefix + truncatedFilename;
  });
}

/**
 * Basic HTML sanitization
 */
function sanitizeHtml(
  input: string,
  allowedTags: string[] = [],
  allowedAttributes: Record<string, string[]> = {}
): string {
  // If no tags are allowed, escape all HTML
  if (allowedTags.length === 0) {
    return escapeHtml(input);
  }

  // For now, implement basic escaping since we don't want HTML in chat
  // In a more complex implementation, you could use a proper HTML sanitizer
  return escapeHtml(input);
}

/**
 * Escapes HTML characters
 */
function escapeHtml(input: string): string {
  const htmlEscapes: Record<string, string> = {
    '&': '&',
    '<': '<',
    '>': '>',
    '"': '"',
    "'": '&#x27;',
    '/': '&#x2F;',
  };

  return input.replace(/[&<>"'/]/g, (char) => htmlEscapes[char]);
}

/**
 * Removes control characters that could cause issues
 */
function removeControlCharacters(input: string): string {
  // Remove null bytes and other problematic control characters
  // Keep newlines, tabs, and spaces
  return input.replace(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/g, '');
}

/**
 * Normalizes whitespace while preserving intentional formatting
 */
function normalizeWhitespace(input: string): string {
  // Replace multiple spaces with single space (but preserve newlines)
  return input
    .replace(/[ \t]+/g, ' ') // Multiple spaces/tabs to single space
    .replace(/\n{3,}/g, '\n\n') // Maximum two consecutive newlines
    .trim();
}

/**
 * Validates that the sanitized input meets basic requirements
 */
export function validateChatMessage(input: string): { isValid: boolean; error?: string } {
  if (!input || input.trim().length === 0) {
    return { isValid: false, error: 'Message cannot be empty' };
  }

  if (input.length > 10000) {
    return { isValid: false, error: 'Message is too long (maximum 10000 characters)' };
  }

  // Check for suspicious patterns
  const suspiciousPatterns = [
    /<script/i,
    /javascript:/i,
    /on\w+\s*=/i,
    /data:\s*text\/html/i,
  ];

  for (const pattern of suspiciousPatterns) {
    if (pattern.test(input)) {
      return { isValid: false, error: 'Message contains potentially harmful content' };
    }
  }

  return { isValid: true };
}

/**
 * Combined sanitization and validation function
 */
export function sanitizeAndValidateChatMessage(
  input: string,
  options: Partial<SanitizationOptions> = {}
): { sanitized: string; isValid: boolean; error?: string } {
  const sanitized = sanitizeChatMessage(input, options);
  const validation = validateChatMessage(sanitized);

  return {
    sanitized,
    isValid: validation.isValid,
    error: validation.error,
  };
}