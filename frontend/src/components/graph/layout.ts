import dagre from '@dagrejs/dagre'
import type { Edge, Node } from '@xyflow/react'
import type { GraphEdgeDto, GraphNodeDto } from '../../types'

const NODE_WIDTH = 240
const NODE_HEIGHT = 90

export function getLayoutedElements(
  nodes: Node[],
  edges: Edge[],
  direction: 'LR' | 'TB' = 'LR'
): { nodes: Node[]; edges: Edge[] } {
  const dagreGraph = new dagre.graphlib.Graph()
  dagreGraph.setDefaultEdgeLabel(() => ({}))

  const isHorizontal = direction === 'LR'
  dagreGraph.setGraph({
    rankdir: direction,
    nodesep: 50,
    ranksep: 90,
  })

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT })
  })

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target)
  })

  dagre.layout(dagreGraph)

  const layoutedNodes = nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id)
    return {
      ...node,
      targetPosition: isHorizontal ? 'left' : 'top',
      sourcePosition: isHorizontal ? 'right' : 'bottom',
      position: {
        x: nodeWithPosition.x - NODE_WIDTH / 2,
        y: nodeWithPosition.y - NODE_HEIGHT / 2,
      },
    }
  })

  return { nodes: layoutedNodes as Node[], edges }
}

export function transformApiGraph(
  apiNodes: GraphNodeDto[],
  apiEdges: GraphEdgeDto[],
  direction: 'LR' | 'TB' = 'LR'
): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = apiNodes.map((n) => ({
    id: n.id,
    type: n.type,
    data: n.data,
    position: { x: 0, y: 0 },
  }))

  const edges: Edge[] = apiEdges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    label: e.label,
    data: e.data,
    animated: e.data.relation_type === 'DRIVES' || e.data.relation_type === 'CALCULATED_FROM',
    style: {
      stroke:
        e.data.relation_type === 'OFFSETS'
          ? '#ef4444'
          : e.data.relation_type === 'DRIVES'
          ? '#10b981'
          : '#6366f1',
      strokeWidth: 2,
    },
  }))

  return getLayoutedElements(nodes, edges, direction)
}
