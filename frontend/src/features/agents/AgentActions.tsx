import { useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Copy, LoaderCircle, MoreHorizontal, Pencil, Trash2 } from 'lucide-react';
import { api } from '../../api';
import { isActive } from '../../history-types';
import { Modal, ErrorNotice } from '../../components/ui';
import type { Agent } from '../../types';
import { AgentEditor } from './AgentEditor';
export function AgentActions({
  agent,
  onSaved,
  onDeleted,
  disabled,
}: {
  agent: Agent;
  onSaved: (agent: Agent) => void;
  onDeleted: () => void;
  disabled?: boolean;
}) {
  const [mode, setMode] = useState<'edit' | 'duplicate' | 'delete' | null>(null);
  const menu = useRef<HTMLDetailsElement>(null);
  function choose(value: typeof mode) {
    if (disabled) return;
    if (menu.current) menu.current.open = false;
    setMode(value);
  }
  return (
    <>
      <details className="agent-actions-menu" ref={menu}>
        <summary aria-label="Manage agent">
          <MoreHorizontal size={19} />
          <span>Manage</span>
        </summary>
        <div className="agent-actions-popover">
          <button disabled={disabled} onClick={() => choose('edit')}>
            <Pencil size={16} /> Edit agent
          </button>
          <button disabled={disabled} onClick={() => choose('duplicate')}>
            <Copy size={16} /> Duplicate agent
          </button>
          <button disabled={disabled} className="danger-text" onClick={() => choose('delete')}>
            <Trash2 size={16} /> Delete agent
          </button>
        </div>
      </details>
      {(mode === 'edit' || mode === 'duplicate') && (
        <AgentEditor
          initialAgent={agent}
          mode={mode}
          onCreated={onSaved}
          onClose={() => setMode(null)}
        />
      )}
      {mode === 'delete' && (
        <DeleteAgent agent={agent} onDeleted={onDeleted} onClose={() => setMode(null)} />
      )}
    </>
  );
}
function DeleteAgent({
  agent,
  onDeleted,
  onClose,
}: {
  agent: Agent;
  onDeleted: () => void;
  onClose: () => void;
}) {
  const client = useQueryClient();
  const tasks = useQuery({
    queryKey: ['tasks', agent.id],
    queryFn: () => api.tasks(agent.id),
    refetchInterval: 1200,
  });
  const active = tasks.data?.some(isActive);
  const remove = useMutation({
    mutationFn: () => api.deleteAgent(agent.id),
    onSuccess: () => {
      client.setQueryData<Agent[]>(['agents'], (old) => old?.filter((a) => a.id !== agent.id));
      client.removeQueries({ queryKey: ['tasks', agent.id] });
      client.invalidateQueries({ queryKey: ['agents'] });
      client.invalidateQueries({ queryKey: ['history'] });
      onDeleted();
      onClose();
    },
  });
  return (
    <Modal
      title={`Delete ${agent.name}?`}
      onClose={() => {
        if (!remove.isPending) onClose();
      }}
    >
      <p className="modal-copy">Previous tasks stay in History. This agent will be removed.</p>
      {tasks.isError && <ErrorNotice error={tasks.error} retry={() => tasks.refetch()} />}
      {active && (
        <div className="info-box" role="status">
          Finish this agent’s current task or payment approval first.{' '}
          <Link to={`/chat/${agent.id}`}>Open chat</Link>
        </div>
      )}
      {remove.isError && <ErrorNotice error={remove.error} />}
      <div className="dialog-actions">
        <button className="secondary" disabled={remove.isPending} onClick={onClose}>
          Cancel
        </button>
        <button
          className="danger-button"
          disabled={tasks.isPending || tasks.isError || active || remove.isPending}
          onClick={() => remove.mutate()}
        >
          {remove.isPending ? <LoaderCircle size={17} className="spin" /> : <Trash2 size={17} />}{' '}
          Delete agent
        </button>
      </div>
    </Modal>
  );
}
