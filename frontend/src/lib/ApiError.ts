export enum ErrorType {
  NETWORK_ERROR = 'NETWORK_ERROR',
  AUTHENTICATION_ERROR = 'AUTHENTICATION_ERROR',
  AUTHORIZATION_ERROR = 'AUTHORIZATION_ERROR',
  VALIDATION_ERROR = 'VALIDATION_ERROR',
  NOT_FOUND_ERROR = 'NOT_FOUND_ERROR',
  CONFLICT_ERROR = 'CONFLICT_ERROR',
  RATE_LIMIT_ERROR = 'RATE_LIMIT_ERROR',
  SERVER_ERROR = 'SERVER_ERROR',
  UNKNOWN_ERROR = 'UNKNOWN_ERROR',
}

export interface ErrorDetails {
  field?: string;
  value?: any;
  code?: string;
  [key: string]: any;
}

export class ApiError extends Error {
  public readonly type: ErrorType;
  public readonly statusCode: number;
  public readonly details?: ErrorDetails;
  public readonly timestamp: string;
  public readonly isRetryable: boolean;
  public readonly originalError?: Error;

  constructor(
    type: ErrorType,
    message: string,
    statusCode: number = 500,
    details?: ErrorDetails,
    originalError?: Error
  ) {
    super(message);
    this.name = 'ApiError';
    this.type = type;
    this.statusCode = statusCode;
    this.details = details;
    this.timestamp = new Date().toISOString();
    this.originalError = originalError;

    // Determine if error is retryable based on type and status code
    this.isRetryable = this.determineRetryability();

    // Maintain proper stack trace
    if (Error.captureStackTrace) {
      Error.captureStackTrace(this, ApiError);
    }
  }

  private determineRetryability(): boolean {
    // Network errors are generally retryable
    if (this.type === ErrorType.NETWORK_ERROR) {
      return true;
    }

    // Server errors (5xx) are generally retryable
    if (this.statusCode >= 500) {
      return true;
    }

    // Rate limit errors are retryable after a delay
    if (this.type === ErrorType.RATE_LIMIT_ERROR) {
      return true;
    }

    // Authentication errors are not retryable
    if (this.type === ErrorType.AUTHENTICATION_ERROR) {
      return false;
    }

    // Client errors (4xx) are generally not retryable
    if (this.statusCode >= 400 && this.statusCode < 500) {
      return false;
    }

    return false;
  }

  static fromResponse(response: Response, data?: any): ApiError {
    const statusCode = response.status;
    const errorData = data || {};

    let type: ErrorType;
    let message = errorData.message || `HTTP ${statusCode}: ${response.statusText}`;

    // Map HTTP status codes to error types
    switch (statusCode) {
      case 400:
        type = ErrorType.VALIDATION_ERROR;
        break;
      case 401:
        type = ErrorType.AUTHENTICATION_ERROR;
        message = errorData.message || 'Authentication required';
        break;
      case 403:
        type = ErrorType.AUTHORIZATION_ERROR;
        message = errorData.message || 'Access denied';
        break;
      case 404:
        type = ErrorType.NOT_FOUND_ERROR;
        message = errorData.message || 'Resource not found';
        break;
      case 409:
        type = ErrorType.CONFLICT_ERROR;
        message = errorData.message || 'Resource conflict';
        break;
      case 429:
        type = ErrorType.RATE_LIMIT_ERROR;
        message = errorData.message || 'Rate limit exceeded';
        break;
      case 500:
      case 502:
      case 503:
      case 504:
        type = ErrorType.SERVER_ERROR;
        message = errorData.message || 'Server error';
        break;
      default:
        type = ErrorType.UNKNOWN_ERROR;
    }

    return new ApiError(type, message, statusCode, errorData.details, errorData);
  }

  static fromNetworkError(error: Error): ApiError {
    return new ApiError(
      ErrorType.NETWORK_ERROR,
      'Network request failed',
      0,
      undefined,
      error
    );
  }

  static fromUnknownError(error: any): ApiError {
    if (error instanceof ApiError) {
      return error;
    }

    return new ApiError(
      ErrorType.UNKNOWN_ERROR,
      error?.message || 'An unknown error occurred',
      500,
      undefined,
      error
    );
  }

  // Helper methods for common error checks
  isAuthenticationError(): boolean {
    return this.type === ErrorType.AUTHENTICATION_ERROR;
  }

  isAuthorizationError(): boolean {
    return this.type === ErrorType.AUTHORIZATION_ERROR;
  }

  isNetworkError(): boolean {
    return this.type === ErrorType.NETWORK_ERROR;
  }

  isValidationError(): boolean {
    return this.type === ErrorType.VALIDATION_ERROR;
  }

  isServerError(): boolean {
    return this.type === ErrorType.SERVER_ERROR;
  }

  isRateLimitError(): boolean {
    return this.type === ErrorType.RATE_LIMIT_ERROR;
  }

  // Get user-friendly error message
  getUserMessage(): string {
    switch (this.type) {
      case ErrorType.NETWORK_ERROR:
        return 'Connection failed. Please check your internet connection and try again.';
      case ErrorType.AUTHENTICATION_ERROR:
        return 'Your session has expired. Please sign in again.';
      case ErrorType.AUTHORIZATION_ERROR:
        return 'You do not have permission to perform this action.';
      case ErrorType.VALIDATION_ERROR:
        return this.details?.field
          ? `Invalid ${this.details.field}: ${this.details.value || 'value provided'}`
          : 'Please check your input and try again.';
      case ErrorType.NOT_FOUND_ERROR:
        return 'The requested resource was not found.';
      case ErrorType.CONFLICT_ERROR:
        return 'This action conflicts with existing data.';
      case ErrorType.RATE_LIMIT_ERROR:
        return 'Too many requests. Please wait a moment and try again.';
      case ErrorType.SERVER_ERROR:
        return 'Server error occurred. Please try again later.';
      default:
        return this.message;
    }
  }

  // Convert to plain object for logging/serialization
  toJSON() {
    return {
      name: this.name,
      type: this.type,
      message: this.message,
      statusCode: this.statusCode,
      details: this.details,
      timestamp: this.timestamp,
      isRetryable: this.isRetryable,
      stack: this.stack,
    };
  }
}