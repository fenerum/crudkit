import { detail as detailRegex, list as listRegex } from './urls';

/**
 * Ensures an ID is always a string 
 * @param id Any ID value that needs to be converted to string
 * @returns The ID as a string
 */
export const ensureStringId = (id: any): string => {
  return typeof id === 'string' ? id : String(id);
};

/**
 * Gets the prefix (first 3 characters) of a CrudKit ID
 * If the ID does not follow the CrudKit format, returns null
 * 
 * @param id The ID to extract prefix from
 * @returns The 3-letter prefix if valid CrudKit ID, null otherwise
 */
export const getIdPrefix = (id: any): string | null => {
  const stringId = ensureStringId(id);
  
  // Check if the ID matches the CrudKit format (3 uppercase letters followed by numbers)
  if (detailRegex.test(stringId)) {
    return stringId.slice(0, 3);
  }
  
  return null;
};

/**
 * Checks if a string is a valid object type code (3 uppercase letters)
 * 
 * @param str The string to check
 * @returns True if the string is a valid object type, false otherwise
 */
export const isObjectTypeCode = (str: string): boolean => {
  if (!str) return false;
  return listRegex.test(str);
};