import React, { useState, useEffect, useCallback } from 'react'
import {
  ReactFlow,
  Controls,
  Background,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  type NodeMouseHandler,
  BackgroundVariant,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import { MetricNode } from './MetricNode'
import { DisclosureNode } from './DisclosureNode'
import { CitationDrawer } from './CitationDrawer'
import { getLayoutedElements, transformApiGraph } from './layout'
import { api } from '../../api/client'
import type {
  GraphNodeDto,
  GraphResponseDto,
  SubgraphResponseDto,
} from '../../types'
import {
  Layers,
  Search,
  RotateCcw,
  ArrowRightLeft,
  Filter,
} from 'lucide-react'

const nodeTypes = {
  metricNode: MetricNode,
  disclosureNode: DisclosureNode,
}

interface CausalGraphCanvasProps {
  documentId: string
  rawGraph: GraphResponseDto | null
  onRefresh: () => void
}

export const CausalGraphCanvas: React.FC<CausalGraphCanvasProps> = ({
  documentId,
  rawGraph,
  onRefresh,
}) => {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])

  const [direction, setDirection] = useState<'LR' | 'TB'>('LR')
  const [showDisclosures, setShowDisclosures] = useState<boolean>(true)
  const [searchQuery, setSearchQuery] = useState<string>('')

  const [selectedNode, setSelectedNode] = useState<GraphNodeDto | null>(null)
  const [nodeSubgraph, setNodeSubgraph] = useState<SubgraphResponseDto | null>(null)

  // Initialize and filter graph
  useEffect(() => {
    if (!rawGraph) return

    let filteredNodes = rawGraph.nodes || []
    if (!showDisclosures) {
      filteredNodes = filteredNodes.filter((n) => n.type !== 'disclosureNode')
    }

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase()
      filteredNodes = filteredNodes.filter((n) =>
        n.label.toLowerCase().includes(q)
      )
    }

    const validNodeIds = new Set(filteredNodes.map((n) => n.id))
    const rawEdges = rawGraph.edges || []
    const filteredEdges = rawEdges.filter(
      (e) => validNodeIds.has(e.source) && validNodeIds.has(e.target)
    )

    const layouted = transformApiGraph(filteredNodes, filteredEdges)
    setNodes(layouted.nodes)
    setEdges(layouted.edges)
  }, [rawGraph, showDisclosures, searchQuery, setNodes, setEdges])

  // Handle re-layout when direction changes
  const handleToggleDirection = useCallback(() => {
    const nextDir = direction === 'LR' ? 'TB' : 'LR'
    setDirection(nextDir)
    const relayouted = getLayoutedElements(nodes, edges, nextDir)
    setNodes(relayouted.nodes)
    setEdges(relayouted.edges)
  }, [direction, nodes, edges, setNodes, setEdges])

  // Node selection & dependency fetching
  const handleNodeClick: NodeMouseHandler = useCallback(
    async (_, clickedNode) => {
      const allNodes = rawGraph?.nodes || []
      const originalDto = allNodes.find((n) => n.id === clickedNode.id) || null
      setSelectedNode(originalDto)

      if (originalDto) {
        try {
          const sub = await api.getNodeDependencies(documentId, clickedNode.id)
          setNodeSubgraph(sub)
        } catch (err) {
          console.error('Failed to load dependencies for node', clickedNode.id, err)
        }
      }
    },
    [rawGraph, documentId]
  )

  const handleSelectSubNode = useCallback(
    async (nodeId: string) => {
      const allNodes = rawGraph?.nodes || []
      const targetDto = allNodes.find((n) => n.id === nodeId) || null
      setSelectedNode(targetDto)
      if (targetDto) {
        try {
          const sub = await api.getNodeDependencies(documentId, nodeId)
          setNodeSubgraph(sub)
        } catch (err) {
          console.error('Failed to load dependencies', nodeId, err)
        }
      }
    },
    [rawGraph, documentId]
  )

  const stats = (rawGraph?.stats || {}) as Record<string, any>
  const metricCount = stats.metric_nodes !== undefined ? Number(stats.metric_nodes) : nodes.length
  const edgeCount = stats.causal_edges !== undefined ? Number(stats.causal_edges) : edges.length

  return (
    <div className="relative w-full h-[calc(100vh-140px)] bg-slate-950 rounded-2xl overflow-hidden border border-slate-800 shadow-2xl">
      {/* Top Toolbar */}
      <div className="absolute top-4 left-4 z-20 flex flex-wrap items-center gap-2.5 bg-slate-900/90 backdrop-blur-md px-4 py-2.5 rounded-xl border border-slate-800 shadow-lg">
        {/* Search */}
        <div className="relative flex items-center">
          <Search className="w-4 h-4 text-slate-400 absolute left-2.5 pointer-events-none" />
          <input
            type="text"
            placeholder="Search metric..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-8 pr-3 py-1.5 text-xs rounded-lg bg-slate-950 border border-slate-800 text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 w-44"
          />
        </div>

        <div className="h-4 w-px bg-slate-800" />

        {/* Direction Toggle */}
        <button
          onClick={handleToggleDirection}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 transition-colors cursor-pointer"
          title="Toggle Layout Direction (Horizontal / Vertical)"
        >
          <ArrowRightLeft className="w-3.5 h-3.5" />
          <span>{direction === 'LR' ? 'Horizontal (LR)' : 'Vertical (TB)'}</span>
        </button>

        {/* Disclosure Nodes Toggle */}
        <button
          onClick={() => setShowDisclosures(!showDisclosures)}
          className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-colors border cursor-pointer ${
            showDisclosures
              ? 'bg-purple-950/60 border-purple-800 text-purple-300'
              : 'bg-slate-800 border-slate-700 text-slate-400'
          }`}
          title="Toggle Footnote Narrative Nodes"
        >
          <Filter className="w-3.5 h-3.5" />
          <span>Footnotes</span>
        </button>

        {/* Refresh */}
        <button
          onClick={onRefresh}
          className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors cursor-pointer"
          title="Reset View"
        >
          <RotateCcw className="w-4 h-4" />
        </button>
      </div>

      {/* Graph Stats Badge */}
      {rawGraph && (
        <div className="absolute top-4 right-4 z-20 flex items-center gap-3 bg-slate-900/90 backdrop-blur-md px-4 py-2 rounded-xl border border-slate-800 text-xs text-slate-400 shadow-lg">
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-400" />
            <strong className="text-white font-mono">{metricCount}</strong> Metrics
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-indigo-400" />
            <strong className="text-white font-mono">{edgeCount}</strong> Causal Edges
          </span>
        </div>
      )}

      {/* Empty State */}
      {nodes.length === 0 && (
        <div className="absolute inset-0 flex flex-col items-center justify-center z-10 text-center px-4">
          <Layers className="w-12 h-12 text-slate-700 mb-3" />
          <h3 className="text-base font-semibold text-slate-300">No Graph Nodes Available</h3>
          <p className="text-xs text-slate-500 max-w-sm mt-1">
            Please ingest a financial report PDF or load a sample 10-K to generate the causal property graph.
          </p>
        </div>
      )}

      {/* React Flow Viewport */}
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={handleNodeClick}
        fitView
        colorMode="dark"
        className="bg-slate-950"
      >
        <Background variant={BackgroundVariant.Dots} gap={16} size={1} color="#334155" />
        <Controls className="bg-slate-900 border-slate-800 fill-slate-200" />
        <MiniMap
          nodeStrokeColor="#6366f1"
          nodeColor="#1e293b"
          maskColor="rgba(15, 23, 42, 0.7)"
          className="bg-slate-900/80 border border-slate-800 rounded-xl overflow-hidden"
        />
      </ReactFlow>

      {/* Slide-out Citation & Dependency Drawer */}
      <CitationDrawer
        node={selectedNode}
        subgraph={nodeSubgraph}
        onClose={() => setSelectedNode(null)}
        onSelectNode={handleSelectSubNode}
      />
    </div>
  )
}
