# Frontend Unit Tests

This directory contains unit tests for the frontend application.

## Running Tests

To run all tests:

```bash
npm test
```

To run specific test suites:

```bash
npm test -- --testPathPattern="utils|merge" --watchAll=false
```

## Test Structure

Tests are organized in directories that mirror the application structure:

- `__tests__/merge/` - Tests for the merge functionality (CRUD operations)
- `__tests__/utils/` - Tests for utility functions
  - `groupby.test.js` - Tests for groupBy data organization utility
  - `urls.test.js` - Tests for URL generation and validation
  - `fieldpairs.test.js` - Tests for form field layout generation

## Test Coverage

The tests cover these essential areas of functionality:

1. **URL Handling**
   - URL generation for different model types (list/detail)
   - URL generation for different actions (create/edit/delete/merge)
   - Query parameter handling
   - URL validation

2. **Data Manipulation**
   - Data grouping with `groupBy` utility
   - Form field organization with `fieldpairs` utility

3. **Merge Functionality**
   - Object merging with validation
   - Proper ID handling in merge operations
   - Error handling for merge operations

## Writing New Tests

When writing new tests, follow these guidelines:

1. Create test files in the appropriate directory with a `.test.js` extension
2. Use descriptive test names that explain what is being tested
3. Properly mock external dependencies
4. Test both success and failure scenarios
5. Follow the Arrange-Act-Assert pattern

## Example Test Pattern

```javascript
describe('Component/Feature Name', () => {
  beforeEach(() => {
    // Setup and mock dependencies
  });

  test('should handle successful scenario', async () => {
    // Arrange
    // Act
    // Assert
  });

  test('should handle error scenario', async () => {
    // Arrange
    // Act
    // Assert
  });
});
```

## Future Test Improvements

To expand test coverage, consider adding tests for:

1. **API Client** - Test the CrudKitAPIClient class methods
2. **Authentication** - Test login, logout, and token refresh
3. **Form Hooks** - Test form data handling and validation
4. **Components** - Test UI component rendering and interactions
5. **Integration Tests** - Test components working together