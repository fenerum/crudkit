import * as React from "react";
import BaseField, { BaseFieldProps } from "./BaseField";
import { inputClass } from "./inputClass";

type ImageFieldProps = BaseFieldProps;

function convertBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const fileReader = new FileReader();
    fileReader.readAsDataURL(file);
    fileReader.onload = () => resolve(fileReader.result as string);
    fileReader.onerror = (error) => reject(error);
  });
}

export default function ImageField({
  fieldName,
  defaultValue = "",
  metadata,
  ...rest
}: ImageFieldProps) {
  const [hasNewImage, setHasNewImage] = React.useState<boolean>(false);

  return (
    <BaseField
      fieldName={fieldName}
      defaultValue=""
      metadata={metadata}
      rules={{
        validate: {
          required: () => {
            if (metadata.required && !hasNewImage && !defaultValue) {
              return "This field is required";
            }
            return true;
          }
        }
      }}
      {...rest}
    >
      {({ value, onChange, onBlur, hasError, ref }) => {
        const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
          const file = event.target.files?.[0];
          if (file) {
            try {
              const base64 = await convertBase64(file);
              onChange(base64);
              setHasNewImage(true);
            } catch (error) {
              console.error('Error converting file to base64:', error);
            }
          }
        };

        return (
          <div className="col-span-full">
            <div className="mt-2 flex items-center gap-x-3">
              {(value || defaultValue) ? (
                <img
                  className="h-12 w-12 object-cover rounded-md"
                  src={value || defaultValue}
                  alt=""
                />
              ) : (
                <div className="h-12 w-12 rounded-md bg-bg-3 border border-border-1" />
              )}
              <input
                type="file"
                required={metadata.required && !value && !defaultValue}
                accept="image/*"
                className={inputClass(hasError)}
                onChange={handleFileUpload}
                onBlur={onBlur}
                ref={ref}
              />
            </div>
          </div>
        );
      }}
    </BaseField>
  );
}
