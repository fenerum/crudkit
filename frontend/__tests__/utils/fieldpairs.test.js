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
    // The record's own fields come first, the ID after them; 'deleted' is left out
    expect(result).toEqual([
      ['name', 'email'],
      ['phone'],
      ['id'],
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
      ['name', 'active'],
      ['id'],
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
    expect(result).toEqual([
      ['name', 'email'],
      ['phone', 'address'],
      ['id'],
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
      ['name'],
      ['id'],
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
      ['name'],
      ['id'],
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
      ['name'],
      ['id'],
    ]);
  });
});
test('puts bookkeeping fields after the record\'s own, paired among themselves', () => {
  const metadata = {
    fields: { id: {}, created_by: {}, created_at: {}, name: {}, updated_by: {}, updated_at: {}, author: {}, published: {} },
  };
  expect(generateFieldPairs(metadata)).toEqual([
    ['name', 'author'],
    ['published'],
    ['id', 'created_by'],
    ['created_at', 'updated_by'],
    ['updated_at'],
  ]);
});

describe('generateFieldPairs with fields the person may not see', () => {
  const metadata = { fields: { name: {}, email: {}, phone: {} } };

  test('leaves hidden fields out of a flat layout', () => {
    expect(generateFieldPairs(metadata, { fields: ['name', 'special_terms', 'email', 'phone'] })).toEqual([
      ['name', 'email'],
      ['phone'],
    ]);
  });

  test('leaves hidden fields out of a paired layout and drops emptied pairs', () => {
    expect(generateFieldPairs(metadata, { fields: [['name', 'special_terms'], ['special_terms'], ['phone']] })).toEqual([
      ['name'],
      ['phone'],
    ]);
  });
});
