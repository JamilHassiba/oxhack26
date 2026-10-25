import { useState, type FormEvent } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { LoaderCircle, Plus } from 'lucide-react';
import { api } from '../../api';
import { tools } from '../../config';
import { Modal, ErrorNotice } from '../../components/ui';
import type { Agent, AgentInput, Tool } from '../../types';
export function AgentEditor({
  onClose,
  onCreated,
  initialAgent,
  mode = 'create',
}: {
  onClose: () => void;
  onCreated?: (agent: Agent) => void;
  initialAgent?: Agent;
  mode?: 'create' | 'edit';
}) {
  const client = useQueryClient();
  const [enabled, setEnabled] = useState<Tool[]>(
    initialAgent?.tools || ['phone', 'email', 'calendar', 'payments'],
  );
  const title = mode === 'edit' ? 'Edit agent' : 'Create an agent';
  const submitLabel = mode === 'edit' ? 'Save changes' : 'Create agent';
  const mutation = useMutation({
    mutationFn: (input: AgentInput) =>
      mode === 'edit' && initialAgent
        ? api.updateAgent(initialAgent.id, input)
        : api.createAgent(input),
    onSuccess: (agent) => {
      client.invalidateQueries({ queryKey: ['agents'] });
      onCreated?.(agent);
      onClose();
    },
  });
  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    const input: AgentInput = {
      name: String(data.get('name')).trim(),
      tools: enabled,
    };
    if (input.name) mutation.mutate(input);
  }
  return (
    <Modal
      title={title}
      onClose={() => {
        if (!mutation.isPending) onClose();
      }}
    >
      <form onSubmit={submit}>
        <label>
          Agent name
          <input
            name="name"
            placeholder="e.g. Maya"
            required
            maxLength={40}
            autoFocus
            defaultValue={initialAgent?.name || ''}
            disabled={mutation.isPending}
          />
        </label>
        <fieldset disabled={mutation.isPending}>
          <legend>Tools</legend>
          <div className="tool-options">
            {Object.entries(tools).map(([key, tool]) => {
              const Icon = tool.icon;
              return (
                <label
                  key={key}
                  className={`tool-option ${enabled.includes(key as Tool) ? 'selected' : ''}`}
                >
                  <Icon size={19} />
                  <span>
                    <strong>{tool.label}</strong>
                    <small>{tool.description}</small>
                  </span>
                  <input
                    type="checkbox"
                    checked={enabled.includes(key as Tool)}
                    onChange={(e) =>
                      setEnabled(
                        e.target.checked
                          ? [...enabled, key as Tool]
                          : enabled.filter((t) => t !== key),
                      )
                    }
                  />
                </label>
              );
            })}
          </div>
        </fieldset>
        {mutation.isError && <ErrorNotice error={mutation.error} />}
        <button className="primary full" disabled={mutation.isPending}>
          {mutation.isPending ? <LoaderCircle className="spin" size={16} /> : <Plus size={16} />}{' '}
          {submitLabel}
        </button>
      </form>
    </Modal>
  );
}
