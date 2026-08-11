import React, { createContext, useContext } from 'react';
import { FormProvider, useForm } from 'react-hook-form';

// Create the form context
const FormContext = createContext(null);

// Provider component
export function FormContextProvider({ children, defaultValues = {}, formOptions = {} }) {
  const methods = useForm({
    defaultValues,
    mode: 'onBlur',
    ...formOptions
  });

  return (
    <FormContext.Provider value={methods}>
      <FormProvider {...methods}>
        {children}
      </FormProvider>
    </FormContext.Provider>
  );
}

// Hook to use the form context
export function useFormContext() {
  const context = useContext(FormContext);
  if (context === null) {
    throw new Error('useFormContext must be used within a FormContextProvider');
  }
  return context;
}

/**
 * StandaloneFieldWrapper - Provides a FormProvider context for standalone fields
 * Use this when you need to use a field component outside of a form
 * 
 * @param {Object} props Component props
 * @param {React.ReactNode} props.children Child components to render within the form context
 * @param {Object} props.defaultValues Default values for the form fields
 * @param {Object} props.formOptions Additional options for react-hook-form
 * @param {Function} props.onChange Callback function that receives form values when they change
 */
export function StandaloneFieldWrapper({ 
  children, 
  defaultValues = {}, 
  formOptions = {},
  onChange
}) {
  const methods = useForm({
    defaultValues,
    mode: 'onBlur',
    ...formOptions
  });

  // Handle field changes when needed
  React.useEffect(() => {
    if (onChange) {
      const subscription = methods.watch((value) => {
        onChange(value);
      });
      return () => subscription.unsubscribe();
    }
  }, [methods, onChange]);

  return (
    <FormProvider {...methods}>
      {children}
    </FormProvider>
  );
}