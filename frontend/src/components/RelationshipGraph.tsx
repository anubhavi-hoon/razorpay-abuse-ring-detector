import { useMemo, useState } from 'react';
import type { KeyboardEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import type { GraphNode, GraphEdge } from '../types';
import { formatEntityType } from '../constants';
import './RelationshipGraph.css';

interface Props {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

function graphTypeClass(type: string): string {
  const clean = type.toLowerCase().replaceAll('_', '-');
  return `graph-type--${clean}`;
}

function getNodeMeaning(node: GraphNode, count: number): string {
  const countLabel = `${count} ${count === 1 ? 'account' : 'accounts'}`;
  const t = node.type.toLowerCase().replace(/_id$|_hash$/, '');
  switch (t) {
    case 'account':
      return `This account reuses ${count} shared ${count === 1 ? 'identifier' : 'identifiers'} in this ring.`;
    case 'device':
      return `This device identifier was reused across ${countLabel} in this ring.`;
    case 'ip':
    case 'ip_address':
      return `This IP address was used by ${countLabel} during registration or transactions.`;
    case 'payment_instrument':
      return `This payment method was reused by ${countLabel}.`;
    case 'email':
      return `This email hash is shared across ${countLabel}.`;
    case 'phone':
      return `This phone number hash is shared across ${countLabel}.`;
    case 'promotion':
      return `This promotion was claimed by ${countLabel}.`;
    case 'merchant':
      return `This merchant received transactions from ${countLabel}.`;
    default:
      return `This signal connects ${countLabel} in this ring.`;
  }
}

/** Deterministic, interactive bipartite view of accounts and shared identifiers. */
export default function RelationshipGraph({ nodes, edges }: Props) {
  const navigate = useNavigate();
  const [activeType, setActiveType] = useState('all');
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  const { accountNodes, entityNodes, nodeById, entityTypes } = useMemo(() => {
    const accounts: GraphNode[] = [];
    const entities: GraphNode[] = [];
    const byId = new Map<string, GraphNode>();
    for (const node of nodes) {
      byId.set(node.id, node);
      if (node.type === 'account') accounts.push(node);
      else entities.push(node);
    }
    return {
      accountNodes: accounts,
      entityNodes: entities,
      nodeById: byId,
      entityTypes: [...new Set(entities.map((node) => node.type))],
    };
  }, [nodes]);

  const visibleEdges = useMemo(
    () =>
      activeType === 'all'
        ? edges
        : edges.filter((edge) => edge.type === activeType),
    [activeType, edges],
  );

  const activeNodeId = hoveredNodeId ?? selectedNodeId;
  const connectedNodeIds = useMemo(() => {
    const connected = new Set<string>();
    if (!activeNodeId) return connected;
    connected.add(activeNodeId);
    for (const edge of visibleEdges) {
      if (edge.source === activeNodeId) connected.add(edge.target);
      if (edge.target === activeNodeId) connected.add(edge.source);
    }
    return connected;
  }, [activeNodeId, visibleEdges]);

  const focusedNode = activeNodeId ? nodeById.get(activeNodeId) : undefined;
  const focusedEdges = activeNodeId
    ? visibleEdges.filter(
        (edge) => edge.source === activeNodeId || edge.target === activeNodeId,
      )
    : [];

  const nodeWidth = 150;
  const entityWidth = 180;
  const nodeHeight = 44;
  const paddingY = 68;
  const rowSpacing = 74;
  const leftX = 150;
  const rightX = 650;
  const svgWidth = 800;
  const maxRows = Math.max(accountNodes.length, entityNodes.length, 1);
  const svgHeight = Math.max(320, paddingY * 2 + (maxRows - 1) * rowSpacing);

  const positions = useMemo(() => {
    const result = new Map<string, { x: number; y: number }>();
    const place = (items: GraphNode[], x: number) => {
      const totalHeight = (items.length - 1) * rowSpacing;
      const startY = (svgHeight - totalHeight) / 2;
      items.forEach((node, index) => {
        result.set(node.id, { x, y: startY + index * rowSpacing });
      });
    };
    place(accountNodes, leftX);
    place(entityNodes, rightX);
    return result;
  }, [accountNodes, entityNodes, svgHeight]);

  function isNodeDimmed(node: GraphNode) {
    if (activeType !== 'all') {
      if (node.type !== 'account' && node.type !== activeType) return true;
      if (
        node.type === 'account' &&
        !visibleEdges.some(
          (edge) => edge.source === node.id || edge.target === node.id,
        )
      ) {
        return true;
      }
    }
    return Boolean(activeNodeId && !connectedNodeIds.has(node.id));
  }

  function toggleNode(nodeId: string) {
    setSelectedNodeId((current) => (current === nodeId ? null : nodeId));
  }

  function handleNodeKeyDown(event: KeyboardEvent, node: GraphNode) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      toggleNode(node.id);
    }
  }

  function handleResetFilters() {
    setActiveType('all');
    setSelectedNodeId(null);
    setHoveredNodeId(null);
  }

  if (nodes.length === 0) {
    return <p className="text-muted">No relationship data is available.</p>;
  }

  const hasActiveFilterOrSelection = activeType !== 'all' || selectedNodeId !== null;

  return (
    <section className="relationship-explorer" aria-labelledby="connection-map-title">
      <div className="graph-intro">
        <div>
          <h2 id="connection-map-title">Connection map</h2>
          <p id="connection-map-help">
            A connection means these accounts reused the same identifier. Select a signal or account to trace its relationships.
          </p>
        </div>
        <div className="graph-counts" aria-label="Graph totals">
          <span><strong>{accountNodes.length}</strong> accounts</span>
          <span><strong>{entityNodes.length}</strong> shared signals</span>
          <span><strong>{edges.length}</strong> connections</span>
        </div>
      </div>

      <div className="graph-filter-bar">
        <div className="graph-filter" aria-label="Filter relationship types">
          <button
            type="button"
            className={activeType === 'all' ? 'is-active' : ''}
            aria-pressed={activeType === 'all'}
            onClick={() => {
              setActiveType('all');
              setSelectedNodeId(null);
            }}
          >
            All signals
          </button>
          {entityTypes.map((type) => (
            <button
              key={type}
              type="button"
              className={`${graphTypeClass(type)} ${activeType === type ? 'is-active' : ''}`}
              aria-pressed={activeType === type}
              onClick={() => {
                setActiveType(type);
                setSelectedNodeId(null);
              }}
            >
              <span className="graph-filter-dot" aria-hidden="true" />
              {formatEntityType(type)}
            </button>
          ))}
        </div>

        {hasActiveFilterOrSelection && (
          <button
            type="button"
            className="graph-reset-btn"
            onClick={handleResetFilters}
            aria-label="Clear active signal filter and selection"
          >
            Reset view
          </button>
        )}
      </div>

      <div className="graph-stage">
        <div className="relationship-graph-container">
          <svg
            className="relationship-graph"
            viewBox={`0 0 ${svgWidth} ${svgHeight}`}
            role="img"
            aria-labelledby="connection-map-title connection-map-help"
          >
            <text x={leftX - nodeWidth / 2} y="28" className="graph-col-label">
              Ring accounts
            </text>
            <text x={rightX - entityWidth / 2} y="28" className="graph-col-label">
              Reused identifiers
            </text>

            <g className="graph-edges" aria-hidden="true">
              {visibleEdges.map((edge, index) => {
                const from = positions.get(edge.source);
                const to = positions.get(edge.target);
                if (!from || !to) return null;
                const related =
                  !activeNodeId ||
                  edge.source === activeNodeId ||
                  edge.target === activeNodeId;
                const startX = from.x + nodeWidth / 2;
                const endX = to.x - entityWidth / 2;
                const curve = (endX - startX) * 0.48;
                return (
                  <path
                    key={`${edge.source}-${edge.target}-${edge.type}`}
                    d={`M ${startX} ${from.y} C ${startX + curve} ${from.y}, ${endX - curve} ${to.y}, ${endX} ${to.y}`}
                    className={`graph-edge ${graphTypeClass(edge.type)} ${related ? 'is-related' : 'is-dimmed'}`}
                    style={{ animationDelay: `${Math.min(index * 35, 420)}ms` }}
                    pathLength="1"
                  />
                );
              })}
            </g>

            {accountNodes.map((node) => {
              const position = positions.get(node.id);
              if (!position) return null;
              const isSelected = selectedNodeId === node.id;
              return (
                <g
                  key={node.id}
                  className={`graph-node graph-node--account ${isNodeDimmed(node) ? 'is-dimmed' : ''} ${activeNodeId === node.id ? 'is-active' : ''} ${isSelected ? 'is-selected' : ''}`}
                  tabIndex={0}
                  role="button"
                  aria-pressed={isSelected}
                  aria-label={`Account ${node.label}, select to trace connected identifiers`}
                  onMouseEnter={() => setHoveredNodeId(node.id)}
                  onMouseLeave={() => setHoveredNodeId(null)}
                  onFocus={() => setHoveredNodeId(node.id)}
                  onBlur={() => setHoveredNodeId(null)}
                  onClick={() => toggleNode(node.id)}
                  onKeyDown={(event) => handleNodeKeyDown(event, node)}
                >
                  <rect
                    x={position.x - nodeWidth / 2}
                    y={position.y - nodeHeight / 2}
                    width={nodeWidth}
                    height={nodeHeight}
                    rx="6"
                  />
                  <circle cx={position.x - nodeWidth / 2 + 16} cy={position.y} r="4" />
                  <text x={position.x - nodeWidth / 2 + 28} y={position.y + 4} className="graph-node-label">
                    {node.label}
                  </text>
                </g>
              );
            })}

            {entityNodes.map((node) => {
              const position = positions.get(node.id);
              if (!position) return null;
              const connectionCount = edges.filter(
                (edge) => edge.source === node.id || edge.target === node.id,
              ).length;
              const isSelected = selectedNodeId === node.id;
              return (
                <g
                  key={node.id}
                  className={`graph-node graph-node--entity ${graphTypeClass(node.type)} ${isNodeDimmed(node) ? 'is-dimmed' : ''} ${activeNodeId === node.id ? 'is-active' : ''} ${isSelected ? 'is-selected' : ''}`}
                  tabIndex={0}
                  role="button"
                  aria-pressed={isSelected}
                  aria-label={`${formatEntityType(node.type)} ${node.label}, reused by ${connectionCount} accounts`}
                  onMouseEnter={() => setHoveredNodeId(node.id)}
                  onMouseLeave={() => setHoveredNodeId(null)}
                  onFocus={() => setHoveredNodeId(node.id)}
                  onBlur={() => setHoveredNodeId(null)}
                  onClick={() => toggleNode(node.id)}
                  onKeyDown={(event) => handleNodeKeyDown(event, node)}
                >
                  <rect
                    x={position.x - entityWidth / 2}
                    y={position.y - nodeHeight / 2}
                    width={entityWidth}
                    height={nodeHeight}
                    rx="6"
                  />
                  <circle cx={position.x - entityWidth / 2 + 16} cy={position.y} r="4" />
                  <text x={position.x - entityWidth / 2 + 28} y={position.y - 3} className="graph-node-type-label">
                    {formatEntityType(node.type)}
                  </text>
                  <text x={position.x - entityWidth / 2 + 28} y={position.y + 12} className="graph-entity-label">
                    {node.label.length > 20 ? `${node.label.slice(0, 20)}…` : node.label}
                  </text>
                  <text x={position.x + entityWidth / 2 - 12} y={position.y + 4} className="graph-connection-count">
                    {connectionCount}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>

        <aside className={`graph-inspector ${focusedNode ? 'has-focus' : ''}`} aria-live="polite">
          {focusedNode ? (
            <>
              <div className="graph-inspector-header">
                <span className="graph-inspector-kicker">
                  {focusedNode.type === 'account'
                    ? 'Account selected'
                    : `${formatEntityType(focusedNode.type)} signal`}
                </span>
                {selectedNodeId && (
                  <button
                    type="button"
                    className="graph-inspector-clear"
                    onClick={() => setSelectedNodeId(null)}
                    aria-label="Clear node selection"
                  >
                    Clear
                  </button>
                )}
              </div>
              <strong className="mono graph-inspector-label">{focusedNode.label}</strong>
              <p className="graph-inspector-meaning">
                {getNodeMeaning(focusedNode, focusedEdges.length)}
              </p>
              <div className="graph-inspector-stat">
                <span className="graph-inspector-stat-num mono">{focusedEdges.length}</span>
                <span className="graph-inspector-stat-label">
                  {focusedNode.type === 'account' ? 'Linked signals' : 'Linked accounts'}
                </span>
              </div>
              {focusedNode.type === 'account' && (
                <button
                  type="button"
                  className="btn btn-primary graph-open-account-btn"
                  onClick={() => navigate(`/accounts/${focusedNode.id}`)}
                >
                  Open account details <span aria-hidden="true">→</span>
                </button>
              )}
            </>
          ) : (
            <>
              <span className="graph-inspector-kicker">How to read this</span>
              <strong className="graph-inspector-title">Trace shared signals</strong>
              <p className="graph-inspector-help">
                Colored paths connect accounts that shared the same device, IP address, or payment method.
              </p>
              <p className="graph-inspector-hint">
                Select or hover over any account or signal to isolate its connections.
              </p>
            </>
          )}
        </aside>
      </div>
    </section>
  );
}
