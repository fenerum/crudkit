import { useMemo } from 'react';
import { useMutation, useQueries, useQuery } from '@tanstack/react-query';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { toast } from 'react-toastify';
import CrudKitAPIClient from '../../data/api';
import DetailPane from '../../components/DetailPane';
import InlineList from '../../components/InlineList';
import Feed from '../../components/Feed';
import AssistantLauncher from '../../components/Assistant/AssistantLauncher';
import generateFieldPairs from '../../utils/fieldpairs';
import { useHotkeys } from 'react-hotkeys-hook';
import { url } from '../../utils/urls';
import { useTopbarSlots, OverflowMenu, Icon } from '../../components/ui';
import { isFrontendPath } from './is-frontend-path';

function truncateLabel(s: string, max = 18) {
  if (typeof s !== 'string') return '';
  return s.length > max ? s.slice(0, max - 1) + '…' : s;
}

// Render any http(s) URLs inside a toast message as clickable links, leaving the rest
// as plain text. Returns the original string when there's nothing to linkify.
function linkify(text: string) {
  const urlPattern = /(https?:\/\/[^\s]+)/g;
  if (!urlPattern.test(text)) return text;
  const parts = text.split(urlPattern);
  return (
    <>
      {parts.map((part, i) =>
        /^https?:\/\//.test(part) ? (
          <a key={i} href={part} target="_blank" rel="noopener noreferrer" className="underline">
            {part}
          </a>
        ) : (
          part
        )
      )}
    </>
  );
}

function InlineTab({ inline, parent_object_id }: any) {
  const [model, fields, , inlineMetadata, createParams, , related_field_name] = inline;
  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-fg-1 capitalize tracking-tight">
          {inlineMetadata.verbose_name_plural}
        </h3>
        <Link
          to={
            url(model, 'create') +
            (createParams ? '?' + new URLSearchParams(createParams).toString() : '')
          }
          className="ck-btn ck-btn-secondary ck-btn-sm"
        >
          <Icon name="plus" size={12} color="currentColor" />
          New
        </Link>
      </div>
      <InlineList
        fields={fields}
        model={model}
        metadata={inlineMetadata}
        createParams={createParams}
        parent_object_id={parent_object_id}
        related_field_name={related_field_name}
      />
    </div>
  );
}

function DetailWebTabs({ fieldPairs, object, metadata, layout, type, id }: any) {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const client = useMemo(() => new CrudKitAPIClient(), []);

  const hasInlines = !!(layout && layout.inlines && layout.inlines.length > 0);

  const inlinesQuery = useQuery({
    queryKey: ['inlines-metadata', type, id],
    enabled: hasInlines && !!metadata,
    queryFn: async () => {
      return Promise.all(
        layout.inlines.map(async ([mdl, fields]: any) => {
          const related_field_name = metadata.relations.find(
            (r: any) => r.related_model_type === mdl,
          )?.field_name;
          const createParams = related_field_name ? { [related_field_name]: id } : {};
          return [
            mdl,
            fields,
            [],
            await client.metadata(mdl),
            createParams,
            id,
            related_field_name,
          ];
        }),
      );
    },
  });

  const inlines = inlinesQuery.data || [];
  const feedInline = inlines.find(([m]: any) => m === 'FEI');
  const otherInlines = inlines.filter(([m]: any) => m !== 'FEI');

  const inlineCounts = useQueries({
    queries: otherInlines.map(([mdl, , , , , , related_field_name]: any) => ({
      queryKey: ['inline-count', mdl, id],
      enabled: !!related_field_name,
      queryFn: async () => {
        const res = await client.list(mdl, {
          [related_field_name]: id,
          page_size: 1,
          _fields: 'id',
        });
        return res?.count ?? (Array.isArray(res) ? res.length : 0);
      },
    })),
  });

  const tabIds = ['properties'];
  otherInlines.forEach(([mdl]: any) => tabIds.push(`inline-${mdl}`));

  const defaultTab = 'properties';
  const tabParam = searchParams.get('tab');
  const tab = tabParam && tabIds.includes(tabParam) ? tabParam : defaultTab;

  const setTab = (next: string) => {
    if (next === tab) return;
    const params = new URLSearchParams(searchParams);
    if (next === defaultTab) params.delete('tab');
    else params.set('tab', next);
    setSearchParams(params, { replace: true });
  };

  return (
    <div className="flex flex-col">
      <div className="ck-vt-tabs" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'properties'}
          className={`ck-vt-tab ${tab === 'properties' ? 'is-on' : ''}`}
          onClick={() => setTab('properties')}
        >
          <span className="capitalize" title={metadata?.verbose_name}>
            {truncateLabel(metadata?.verbose_name) || 'Properties'}
          </span>
        </button>
        {otherInlines.map((inline: any, i: number) => {
          const [mdl, , , inlineMetadata] = inline;
          const tabId = `inline-${mdl}`;
          const count = inlineCounts[i]?.data;
          const isEmpty = count === 0;
          return (
            <button
              key={mdl}
              type="button"
              role="tab"
              aria-selected={tab === tabId}
              className={`ck-vt-tab ${tab === tabId ? 'is-on' : ''} ${isEmpty ? 'is-empty' : ''}`}
              onClick={() => setTab(tabId)}
            >
              <span className="capitalize" title={inlineMetadata.verbose_name_plural}>
                {truncateLabel(inlineMetadata.verbose_name_plural)}
              </span>
              {count != null && <span className="ck-vt-tab-count">{count}</span>}
            </button>
          );
        })}
      </div>
      <div className="ck-vt-body">
        {tab === 'properties' && (
          <>
            <DetailPane
              field_pairs={fieldPairs}
              object={object}
              metadata={metadata.fields}
              form={null}
            />
            {feedInline && (() => {
              const [mdl, fields, , inlineMetadata, , parent_object_id, related_field_name] = feedInline;
              return (
                <Feed
                  fields={fields}
                  model={mdl}
                  parent_object_id={parent_object_id}
                  metadata={inlineMetadata}
                  related_field_name={related_field_name}
                  parentType={type}
                />
              );
            })()}
          </>
        )}
        {otherInlines.map((inline: any) => {
          const [mdl] = inline;
          if (tab !== `inline-${mdl}`) return null;
          return (
            <InlineTab
              key={mdl}
              inline={inline}
              type={type}
              parent_object_id={id}
            />
          );
        })}
      </div>
    </div>
  );
}

export default function Detail() {
  const { segment } = useParams() as { segment: string };
  const id = segment;
  const type = id.substring(0, 3);
  const navigate = useNavigate();
  const client = useMemo(() => new CrudKitAPIClient(), []);

  const currentUrl = useMemo(() => `/${id}`, [id]);

  useHotkeys('e', () => {
    if (id) navigate(url(id, 'edit', { next: currentUrl }));
  });

  const actionMutation = useMutation({
    mutationFn: (actionName: string) => client.action(type, id, actionName),
    onSuccess: (response: any) => {
      if (response.messages && response.messages.length > 0) {
        response.messages.forEach((message: string) => {
          let displayMessage = message;
          if (message.startsWith('[') && message.endsWith(']')) {
            try {
              const parsed = JSON.parse(message.replace(/'/g, '"'));
              if (Array.isArray(parsed)) displayMessage = parsed[0] || message;
            } catch {
              const match = message.match(/\['(.*?)'\]/);
              if (match && match[1]) displayMessage = match[1];
            }
          }
          if (
            displayMessage.includes('required') ||
            displayMessage.includes('error') ||
            displayMessage.includes('invalid') ||
            displayMessage.includes('failed')
          ) {
            toast.error(linkify(displayMessage));
          } else {
            toast.info(linkify(displayMessage));
          }
        });
      } else {
        toast.success('Action completed successfully');
      }

      if (response.redirect) {
        if (response.open_in_new_tab) {
          window.open(response.redirect, '_blank', 'noopener,noreferrer');
        } else if (response.redirect.startsWith('http')) {
          window.location.href = response.redirect;
        } else if (response.redirect.startsWith('/')) {
          if (isFrontendPath(response.redirect)) {
            navigate(response.redirect);
          } else {
            window.location.href = response.redirect;
          }
        } else {
          navigate(url(response.redirect));
        }
      } else if (!response.messages || response.messages.length === 0) {
        toast.warn('Action did not return redirect');
      }
    },
    onError: (error: any) => {
      toast.error('Action failed: ' + (error.message || 'Unknown error'));
      console.error('Action error:', error);
    },
  });

  const metadataQuery = useQuery({
    queryKey: ['metadata', type],
    queryFn: () => client.metadata(type),
  });

  const layoutsQuery = useQuery({
    queryKey: ['layouts', type],
    queryFn: () => client.list('LAY', { model: type }),
  });

  const objectQuery = useQuery({
    queryKey: ['detail', type, id],
    queryFn: () => client.retrieve(type, id),
  });

  let layoutData: any = null;
  if (!layoutsQuery.isPending && layoutsQuery.data) {
    const layouts = layoutsQuery.data?.isPaginated ? layoutsQuery.data.results : layoutsQuery.data;
    if (Array.isArray(layouts) && layouts.length > 0) layoutData = layouts[0];
  }

  const object = objectQuery.data;
  const metadata = metadataQuery.data;
  const layout = layoutData;
  const ready =
    !objectQuery.isPending &&
    !metadataQuery.isPending &&
    !layoutsQuery.isPending &&
    !objectQuery.isError &&
    !metadataQuery.isError &&
    !layoutsQuery.isError &&
    object &&
    metadata;

  const overflowItems = useMemo(() => {
    if (!ready) return [];
    const items: any[] = [];
    (metadata.actions || []).forEach((action: any) => {
      items.push({
        label: action.verbose_name,
        icon: 'zap',
        onSelect: () => {
          if (window.confirm(`Are you sure you want to ${action.verbose_name.toLowerCase()}?`)) {
            actionMutation.mutate(action.action);
          }
        },
      });
    });
    items.push({
      label: layout ? 'Edit layout' : 'Create layout',
      icon: 'edit-3',
      onSelect: () =>
        navigate(
          layout
            ? url(layout.id, 'edit', { next: currentUrl })
            : url('LAY', 'create', { model: metadata.type, next: currentUrl }),
        ),
    });
    items.push({
      label: 'View changes',
      icon: 'activity',
      onSelect: () => navigate(`/CHG/?related_object=${id}`),
    });
    items.push({
      label: 'Delete',
      icon: 'trash-2',
      tone: 'danger',
      shortcut: 'X',
      onSelect: () => navigate(url(object.id, 'delete')),
    });
    return items;
    // `actionMutation` intentionally omitted: its `.mutate` reference is stable
    // and including the wrapper object would cause `overflowItems` to retain a
    // new identity each render, looping `useTopbarSlots`'s effect.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, metadata, layout, currentUrl, id, object, navigate]);

  useTopbarSlots(() => {
    if (!ready) return {};
    return {
      // The breadcrumb already shows the model and the bolded ID; just append
      // the object's human label inline.
      title: object.label && object.label !== object.id ? { label: object.label } : undefined,
      primary: (
        <Link
          to={url(object.id, 'edit', { next: currentUrl })}
          className="ck-btn ck-btn-primary ck-btn-sm"
        >
          <Icon name="edit-3" size={12} color="currentColor" />
          Edit
          <span className="ck-kbd">E</span>
        </Link>
      ),
      right: <OverflowMenu items={overflowItems} />,
    };
  }, [ready, metadata?.verbose_name, object?.label, object?.id, currentUrl, overflowItems]);

  if (objectQuery.isPending || metadataQuery.isPending || layoutsQuery.isPending) {
    return <div className="px-1 py-6 text-sm text-fg-3 animate-pulse">Loading…</div>;
  }
  if (objectQuery.isError || metadataQuery.isError || layoutsQuery.isError) {
    return <div className="px-1 py-6 text-sm text-danger">Couldn&apos;t load this record.</div>;
  }

  const fieldPairs = generateFieldPairs(metadata, layout);

  return (
    <>
      <DetailWebTabs
        fieldPairs={fieldPairs}
        object={object}
        metadata={metadata}
        layout={layout}
        type={type}
        id={id}
      />
      <AssistantLauncher objectType={type} objectId={id} />
    </>
  );
}
