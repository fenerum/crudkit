import generateFieldPairs from '../../utils/fieldpairs';

describe('generateFieldPairs utility', () => {
  test('generates field pairs from metadata when no layout is provided', () => {
    // Arrange
    const metadata = {
      fields: {
        id: { type: 'IntegerField' },
        name: { type: 'CharField' },
        email: { type: 'EmailField' },
        phone: { type: 'CharField' },
        deleted: { type: 'BooleanField' }, // should be filtered out
      }
    };
    
    // Act
    const result = generateFieldPairs(metadata);
    
    // Assert
    // Should have two pairs: [id, name] and [email, phone]
    // The 'deleted' field should be filtered out
    expect(result).toEqual([
      ['id', 'name'],
      ['email', 'phone'],
    ]);
  });
  
  test('uses layout fields when layout is provided', () => {
    // Arrange
    const metadata = {
      fields: {
        id: { type: 'IntegerField' },
        name: { type: 'CharField' },
        email: { type: 'EmailField' },
        phone: { type: 'CharField' },
        address: { type: 'TextField' },
      }
    };
    
    const layout = {
        fields: ['name', 'email', 'phone'] // Only include these fields
      };
    
    // Act
    const result = generateFieldPairs(metadata, layout);
    
    // Assert
    // Should use only the fields specified in the layout
    expect(result).toEqual([
      ['name', 'email'],
      ['phone'],
    ]);
  });
  
  test('handles already paired fields in layout', () => {
    // Arrange
    const metadata = {
      fields: {
        id: { type: 'IntegerField' },
        name: { type: 'CharField' },
        email: { type: 'EmailField' },
        phone: { type: 'CharField' },
      }
    };
    
    const layout = {
        fields: [
          ['name', 'email'], // Already paired
          ['phone', 'id']   // Already paired
        ]
      };
    
    // Act
    const result = generateFieldPairs(metadata, layout);
    
    // Assert
    // Should preserve the existing pairs
    expect(result).toEqual([
      ['name', 'email'],
      ['phone', 'id'],
    ]);
  });
  
  test('filters out ignored fields', () => {
    // Arrange
    const metadata = {
      fields: {
        id: { type: 'IntegerField' },
        name: { type: 'CharField' },
        deleted: { type: 'BooleanField' }, // Should be ignored
        merged_into: { type: 'ForeignKey' }, // Should be ignored
        active: { type: 'BooleanField' },
      }
    };
    
    // Act
    const result = generateFieldPairs(metadata);
    
    // Assert
    // The 'deleted' and 'merged_into' fields should be filtered out
    expect(result).toEqual([
      ['id', 'name'],
      ['active'],
    ]);
    
    // Additional verification
    const flattenedFields = result.flat();
    expect(flattenedFields).not.toContain('deleted');
    expect(flattenedFields).not.toContain('merged_into');
  });
  
  test('handles odd number of fields', () => {
    // Arrange
    const metadata = {
      fields: {
        id: { type: 'IntegerField' },
        name: { type: 'CharField' },
        email: { type: 'EmailField' },
        phone: { type: 'CharField' },
        address: { type: 'TextField' }, // This makes it an odd number
      }
    };
    
    // Act
    const result = generateFieldPairs(metadata);
    
    // Assert
    // Should have two full pairs and one with a single field
    expect(result).toEqual([
      ['id', 'name'],
      ['email', 'phone'],
      ['address'],
    ]);
  });
  
  test('handles empty fields', () => {
    // Arrange
    const metadata = {
      fields: {}
    };
    
    // Act
    const result = generateFieldPairs(metadata);
    
    // Assert
    expect(result).toEqual([]);
  });
  
  test('handles undefined layout', () => {
    // Arrange
    const metadata = {
      fields: {
        id: { type: 'IntegerField' },
        name: { type: 'CharField' },
      }
    };
    
    // Act
    const result = generateFieldPairs(metadata, undefined);
    
    // Assert
    expect(result).toEqual([
      ['id', 'name'],
    ]);
  });
  
  test('handles empty layout', () => {
    // Arrange
    const metadata = {
      fields: {
        id: { type: 'IntegerField' },
        name: { type: 'CharField' },
      }
    };
    
    // Act
    const result = generateFieldPairs(metadata, null);
    
    // Assert
    // Should fall back to using metadata fields
    expect(result).toEqual([
      ['id', 'name'],
    ]);
  });
  
  test('handles layout without fields property', () => {
    // Arrange
    const metadata = {
      fields: {
        id: { type: 'IntegerField' },
        name: { type: 'CharField' },
      }
    };
    
    // Act
    const result = generateFieldPairs(metadata, [{}]);
    
    // Assert
    // Should fall back to using metadata fields
    expect(result).toEqual([
      ['id', 'name'],
    ]);
  });
});