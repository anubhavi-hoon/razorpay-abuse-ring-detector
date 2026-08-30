import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import type { GraphNode, GraphEdge } from '../types';
import './RelationshipGraph.css';

interface Props {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

/**
 * Deterministic bipartite SVG graph.
 * Account nodes on the left, shared-entity nodes on the right,
 * edges connecting them.
 */
export default function RelationshipGraph({ nodes, edges }: Props) {
  const navigate = useNavigate();

  const { accountNodes, entityNodes } = useMemo(() => {
    const accounts: GraphNode[] = [];
    const entities: GraphNode[] = [];
    for (const node of nodes) {
      if (node.type === 'account') {
        accounts.push(node);
      } else {
        entities.push(node);
      }
    }
    return { accountNodes: accounts, entityNodes: entities };
  }, [nodes]);

  // Layout parameters
  const nodeRadius = 18;
  const paddingX = 60;
  const paddingY = 40;
  const colSpacing = 320;
  const rowSpacing = 60;

  const leftX = paddingX;
  const rightX = paddingX + colSpacing;

  const maxRows = Math.max(accountNodes.length, entityNodes.length, 1);
  const svgWidth = rightX + paddingX + nodeRadius * 2;
  const svgHeight = paddingY * 2 + (maxRows - 1) * rowSpacing + nodeRadius * 2;

  // Position maps
  const positions = useMemo(() => {
    const pos: Record<string, { x: number; y: number }> = {};

    accountNodes.forEach((node, i) => {
      const totalHeight = (accountNodes.length - 1) * rowSpacing;
      const startY = (svgHeight - totalHeight) / 2;
      pos[node.id] = { x: leftX, y: startY + i * rowSpacing };
    });

    entityNodes.forEach((node, i) => {
      const totalHeight = (entityNodes.length - 1) * rowSpacing;
      const startY = (svgHeight - totalHeight) / 2;
      pos[node.id] = { x: rightX, y: startY + i * rowSpacing };
    });

    return pos;
  }, [accountNodes, entityNodes, svgHeight, leftX, rightX]);

  // Edge type → color/dash
  function edgeStyle(type: string) {
    switch (type) {
      case 'device':
        return { stroke: 'hsl(215, 65%, 48%)', dasharray: '' };
      case 'ip':
        return { stroke: 'hsl(280, 50%, 50%)', dasharray: '6 3' };
      case 'payment_instrument':
        return { stroke: 'hsl(38, 85%, 50%)', dasharray: '2 4' };
      default:
        return { stroke: 'hsl(220, 10%, 55%)', dasharray: '4 2' };
    }
  }

  // Entity node shape
  function entityShape(type: string) {
    switch (type) {
      case 'device':
        return 'rect';
      case 'ip':
        return 'diamond';
      default:
        return 'rounded-rect';
    }
  }

  function handleAccountClick(accountId: string) {
    navigate(`/accounts/${accountId}`);
  }

  function handleAccountKeyDown(e: React.KeyboardEvent, accountId: string) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      navigate(`/accounts/${accountId}`);
    }
  }

  if (nodes.length === 0) {
    return <p className="text-muted">No graph data available.</p>;
  }

  return (
    <div className="relationship-graph-container">
      <svg
        className="relationship-graph"
        viewBox={`0 0 ${svgWidth} ${svgHeight}`}
        role="img"
        aria-label="Relationship graph showing accounts and shared entities"
      >
        {/* Column labels */}
        <text x={leftX} y={16} className="graph-col-label">
          Accounts
        </text>
        <text x={rightX} y={16} className="graph-col-label">
          Shared Entities
        </text>

        {/* Edges */}
        {edges.map((edge, i) => {
          const from = positions[edge.source];
          const to = positions[edge.target];
          if (!from || !to) return null;
          const style = edgeStyle(edge.type);
          const midX = (from.x + to.x) / 2;
          const midY = (from.y + to.y) / 2;

          return (
            <g key={i}>
              <line
                x1={from.x + nodeRadius}
                y1={from.y}
                x2={to.x - nodeRadius}
                y2={to.y}
                stroke={style.stroke}
                strokeWidth="1.5"
                strokeDasharray={style.dasharray || undefined}
                opacity="0.6"
              />
              <text
                x={midX}
                y={midY - 6}
                className="graph-edge-label"
                fill={style.stroke}
              >
                {edge.type}
              </text>
            </g>
          );
        })}

        {/* Account nodes (keyboard-accessible links) */}
        {accountNodes.map((node) => {
          const pos = positions[node.id];
          if (!pos) return null;
          return (
            <g
              key={node.id}
              className="graph-node graph-node--account"
              tabIndex={0}
              role="link"
              aria-label={`Account ${node.label}`}
              onClick={() => handleAccountClick(node.id)}
              onKeyDown={(e) => handleAccountKeyDown(e, node.id)}
              style={{ cursor: 'pointer' }}
            >
              <circle
                cx={pos.x}
                cy={pos.y}
                r={nodeRadius}
                fill="hsl(215, 60%, 94%)"
                stroke="hsl(215, 65%, 48%)"
                strokeWidth="1.5"
              />
              <text x={pos.x} y={pos.y + 4} className="graph-node-label">
                {node.label.length > 12
                  ? node.label.slice(0, 12) + '…'
                  : node.label}
              </text>
            </g>
          );
        })}

        {/* Entity nodes */}
        {entityNodes.map((node) => {
          const pos = positions[node.id];
          if (!pos) return null;
          const shape = entityShape(node.type);

          let shapeEl;
          if (shape === 'rect') {
            shapeEl = (
              <rect
                x={pos.x - nodeRadius}
                y={pos.y - nodeRadius}
                width={nodeRadius * 2}
                height={nodeRadius * 2}
                fill="hsl(38, 80%, 94%)"
                stroke="hsl(38, 85%, 50%)"
                strokeWidth="1.5"
              />
            );
          } else if (shape === 'diamond') {
            const r = nodeRadius;
            const points = `${pos.x},${pos.y - r} ${pos.x + r},${pos.y} ${pos.x},${pos.y + r} ${pos.x - r},${pos.y}`;
            shapeEl = (
              <polygon
                points={points}
                fill="hsl(280, 40%, 94%)"
                stroke="hsl(280, 50%, 50%)"
                strokeWidth="1.5"
              />
            );
          } else {
            shapeEl = (
              <rect
                x={pos.x - nodeRadius}
                y={pos.y - nodeRadius}
                width={nodeRadius * 2}
                height={nodeRadius * 2}
                rx="6"
                ry="6"
                fill="hsl(145, 40%, 94%)"
                stroke="hsl(145, 50%, 40%)"
                strokeWidth="1.5"
              />
            );
          }

          return (
            <g key={node.id} className="graph-node graph-node--entity">
              {shapeEl}
              <text x={pos.x} y={pos.y + nodeRadius + 14} className="graph-entity-label">
                {node.label.length > 18
                  ? node.label.slice(0, 18) + '…'
                  : node.label}
              </text>
              <text x={pos.x} y={pos.y + 4} className="graph-node-type-label">
                {node.type.slice(0, 3)}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
