import * as React from "react";
import BaseField, { BaseFieldProps } from "./BaseField";
import BaseWYSIWYGEditor from "./BaseWYSIWYGEditor";

interface EmailWYSIWYGEditorFieldProps extends BaseFieldProps {
  modelType?: string;
}

export default function EmailWYSIWYGEditorField({
  fieldName,
  defaultValue = "",
  metadata,
  modelType,
  ...rest
}: EmailWYSIWYGEditorFieldProps) {
  return (
    <BaseField
      fieldName={fieldName}
      defaultValue={defaultValue}
      metadata={metadata}
      {...rest}
    >
      {({ value, onChange, onBlur, hasError, ref }) => (
        <BaseWYSIWYGEditor
          value={value}
          onChange={onChange}
          onBlur={onBlur}
          hasError={hasError}
          maxHeight="500px"
          modelType={modelType}
        />
      )}
    </BaseField>
  );
}
