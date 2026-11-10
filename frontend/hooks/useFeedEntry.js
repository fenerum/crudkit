import { getIdPrefix } from '../utils/crudkit';
import { useMetadata } from '../utils/formHooks';

// What kind of feed entry the record `ckId` is (its type's `CrudKitSettings.feed_entry`),
// read from the type's metadata. `entry` is null for records that aren't one.
export function useFeedEntry(ckId) {
  const type = ckId ? getIdPrefix(ckId) : null;
  const { metadata, isMetadataLoading } = useMetadata(type);
  return { type, metadata, entry: metadata?.feed_entry || null, isLoading: isMetadataLoading };
}
