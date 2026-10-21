import { render } from '@testing-library/react';
import { FormProvider, useForm } from 'react-hook-form';
import { describe, expect, test } from 'vitest';
import DecimalField from '../../components/Fields/DecimalField';
import MoneyField from '../../components/Fields/MoneyField';

function renderAndGetValues(Field, defaultValue) {
  let form;
  function Wrapper() {
    form = useForm();
    return (
      <FormProvider {...form}>
        <Field fieldName="amount" defaultValue={defaultValue} metadata={{}} />
      </FormProvider>
    );
  }
  render(<Wrapper />);
  return form.getValues();
}

// A null default used to become the string "null", which DRF rejects with
// "A valid number is required."
describe('numeric fields with a null default', () => {
  test('DecimalField submits an empty string', () => {
    expect(renderAndGetValues(DecimalField, null).amount).toBe('');
  });

  test('MoneyField submits an empty string', () => {
    expect(renderAndGetValues(MoneyField, null).amount).toBe('');
  });

  test('DecimalField keeps a real value', () => {
    expect(renderAndGetValues(DecimalField, 12.5).amount).toBe('12.5');
  });
});
