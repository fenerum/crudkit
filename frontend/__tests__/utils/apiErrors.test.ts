import { ValidationError } from '../../data/api';
import { formatApiError } from '../../utils/apiErrors';

describe('formatApiError', () => {
  it('prefixes field errors with the field label', () => {
    const error = new ValidationError('Invalid Request', { close_reason: ['This field is required.'] });
    const fields = { close_reason: { verbose_name: 'Close reason' } };
    expect(formatApiError(error, fields)).toBe('Close reason: This field is required.');
  });

  it('falls back to the field key without metadata', () => {
    const error = new ValidationError('Invalid Request', { stage: ['Not allowed.'] });
    expect(formatApiError(error)).toBe('stage: Not allowed.');
  });

  it('shows non-field errors without a prefix', () => {
    const error = new ValidationError('Invalid Request', {
      non_field_errors: ['Cannot close a deal without lines.'],
      amount: ['Must be positive.'],
    });
    expect(formatApiError(error)).toBe('Cannot close a deal without lines.\namount: Must be positive.');
  });

  it('joins list-form errors', () => {
    const error = new ValidationError('Invalid Request', {});
    (error as any).errors = ['First problem', 'Second problem'];
    expect(formatApiError(error)).toBe('First problem\nSecond problem');
  });

  it('uses the detail of non-validation errors', () => {
    const error: any = new Error('Failed to load data from server\nForbidden');
    error.errorData = { detail: 'You do not have permission to perform this action.' };
    expect(formatApiError(error)).toBe('You do not have permission to perform this action.');
  });

  it('falls back to the error message', () => {
    expect(formatApiError(new Error('Network down'))).toBe('Network down');
  });

  it('returns null when there is nothing to show', () => {
    expect(formatApiError(new Error(''))).toBeNull();
    expect(formatApiError(undefined)).toBeNull();
  });
});
