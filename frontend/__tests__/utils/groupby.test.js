import { groupBy } from '../../utils/groupby';

describe('groupBy utility', () => {
  test('groups array items by a simple property', () => {
    // Arrange
    const testData = [
      { id: 1, category: 'A', value: 'Item 1' },
      { id: 2, category: 'B', value: 'Item 2' },
      { id: 3, category: 'A', value: 'Item 3' },
      { id: 4, category: 'C', value: 'Item 4' },
      { id: 5, category: 'B', value: 'Item 5' },
    ];
    
    // Act
    const result = groupBy(testData, item => item.category);
    
    // Assert
    expect(result).toEqual({
      'A': [
        { id: 1, category: 'A', value: 'Item 1' },
        { id: 3, category: 'A', value: 'Item 3' },
      ],
      'B': [
        { id: 2, category: 'B', value: 'Item 2' },
        { id: 5, category: 'B', value: 'Item 5' },
      ],
      'C': [
        { id: 4, category: 'C', value: 'Item 4' },
      ],
    });
  });
  
  test('groups array items with a transform function', () => {
    // Arrange
    const testData = [
      { id: 1, category: 'A', value: 'Item 1' },
      { id: 2, category: 'B', value: 'Item 2' },
      { id: 3, category: 'A', value: 'Item 3' },
    ];
    
    // Act - Transform each item to just return the ID
    const result = groupBy(testData, item => item.category, item => item.id);
    
    // Assert
    expect(result).toEqual({
      'A': [1, 3],
      'B': [2],
    });
  });
  
  test('handles empty arrays', () => {
    // Arrange
    const testData = [];
    
    // Act
    const result = groupBy(testData, item => item.category);
    
    // Assert
    expect(result).toEqual({});
  });
  
  test('handles complex getter functions', () => {
    // Arrange
    const testData = [
      { id: 1, nested: { group: 'X' }, value: 'Item 1' },
      { id: 2, nested: { group: 'Y' }, value: 'Item 2' },
      { id: 3, nested: { group: 'X' }, value: 'Item 3' },
    ];
    
    // Act - Use a complex getter function that accesses nested properties
    const result = groupBy(testData, item => item.nested.group);
    
    // Assert
    expect(result).toEqual({
      'X': [
        { id: 1, nested: { group: 'X' }, value: 'Item 1' },
        { id: 3, nested: { group: 'X' }, value: 'Item 3' },
      ],
      'Y': [
        { id: 2, nested: { group: 'Y' }, value: 'Item 2' },
      ],
    });
  });
  
  test('handles computed group keys', () => {
    // Arrange
    const testData = [
      { id: 1, value: 5 },
      { id: 2, value: 10 },
      { id: 3, value: 3 },
      { id: 4, value: 12 },
    ];
    
    // Act - Group by computed value (whether value is greater than 5)
    const result = groupBy(testData, item => item.value > 5 ? 'large' : 'small');
    
    // Assert
    expect(result).toEqual({
      'small': [
        { id: 1, value: 5 },
        { id: 3, value: 3 },
      ],
      'large': [
        { id: 2, value: 10 },
        { id: 4, value: 12 },
      ],
    });
  });
});