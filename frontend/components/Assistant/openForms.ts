import { useSyncExternalStore } from 'react';
import type { UseFormReturn } from 'react-hook-form';
import { appConfig } from '../../utils/appConfig';

// The create/edit forms on screen, innermost last, so the assistant fills the
// form the user is looking at: an inline-create modal over a page form wins.
// Module-level like Modal's stack; FormContainer registers while mounted.

export type FieldMeta = { type?: string; editable?: boolean; [key: string]: unknown };

export type OpenForm = {
  type: string;
  mode: 'create' | 'edit';
  recordId?: string;
  metadata: Record<string, FieldMeta>;
  formMethods: UseFormReturn<any>;
  fill: (fields: Record<string, unknown>) => void;
};

const MAX_TEXT = 500;

let forms: OpenForm[] = [];
const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((listener) => listener());
}

export function registerForm(form: OpenForm): () => void {
  forms = [...forms, form];
  emit();
  return () => {
    forms = forms.filter((f) => f !== form);
    emit();
  };
}

export function activeForm(): OpenForm | null {
  return forms[forms.length - 1] ?? null;
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useActiveForm(): OpenForm | null {
  return useSyncExternalStore(subscribe, activeForm);
}

// What the screen block tells the assistant about the open form.
export function formScreen(form: OpenForm, withValues = false) {
  return {
    type_id: form.type,
    mode: form.mode,
    ...(form.recordId && { record_id: form.recordId }),
    ...(withValues && { values: formSnapshot(form) }),
  };
}

// The editable values typed so far, as plain scalars: foreign keys by id,
// money by amount, long text cut short.
export function formSnapshot(form: OpenForm): Record<string, unknown> {
  const values = form.formMethods.getValues();
  const out: Record<string, unknown> = {};
  for (const [name, meta] of Object.entries(form.metadata)) {
    if (!meta?.editable) continue;
    let value = values[name];
    if (value && typeof value === 'object') value = 'id' in value ? value.id : 'amount' in value ? value.amount : null;
    if (typeof value === 'string') value = value.slice(0, MAX_TEXT);
    if (value !== undefined) out[name] = value;
  }
  return out;
}

// A value from the assistant in the shape the field's input holds. Foreign
// keys already arrive as {id, label}; money keeps the currency already chosen.
export function toFormValue(meta: FieldMeta | undefined, value: unknown, current?: unknown): unknown {
  if (meta?.type === 'MoneyField' && value !== null && value !== '' && typeof value !== 'object') {
    const currency = (current as { currency?: string } | null)?.currency || appConfig.default_currency;
    return {
      currency,
      amount: String(value),
      amount_default_currency: String(value),
      default_currency: appConfig.default_currency,
    };
  }
  return value;
}
