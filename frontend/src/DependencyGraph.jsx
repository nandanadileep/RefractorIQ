// RefractorIQ/frontend/src/DependencyGraph.jsx

import React, { useMemo } from 'react';
import ReactFlow, { MiniMap, Controls, Background } from 'reactflow';
import 'reactflow/dist/style.css'; // Ensure styles are imported

// --- Color Palette & Hashing Function ---
// A palette of visually distinct, reasonably pleasant colors
const COLOR_PALETTE = [
  '#a8e6cf', '#dcedc1', '#ffd3b6', '#ffaaa5', '#ff8b94', // Pastels 1
  '#b0e0e6', '#c7b2de', '#fbc4e0', '#f9eac3', '#ace5ee', // Pastels 2
  '#77dd77', '#fdfd96', '#ffb347', '#ff6961', '#aec6cf', // Brighter 1
  '#dea5a4', '#b19cd9', '#f49ac2', '#e6e6fa', '#add8e6', // Brighter 2
  '#fecaca', '#fed7aa', '#fef08a', '#d9f99d', '#bfdbfe', // Tailwind Light Reds/Oranges/Yellows/Greens/Blues
  '#a5f3fc', '#f5d0fe', '#fecdd3', '#e0e7ff', '#ccfbf1'  // Tailwind Light Cyan/Fuchsia/Pink/Indigo/Teal
];

// Simple deterministic function to get a color index based on a string (folder name)
function getFolderColorIndex(folderName) {
  let hash = 0;
  // Use '.' as the key for files directly in the root
  const key = folderName === '.' || !folderName ? '.' : folderName;
  for (let i = 0; i < key.length; i++) {
    const char = key.charCodeAt(i);
    hash = (hash << 5) - hash + char;
    hash |= 0; // Convert to 32bit integer
  }
  return Math.abs(hash);
}
// --- END Color Logic ---


// --- Layout and Styling Function ---
const getLayoutedElements = (nodes, edges) => {
  if (!nodes || nodes.length === 0) {
    return { layoutedNodes: [], layoutedEdges: edges || [] };
  }

  // Keep track of assigned folder colors
  const folderColorMap = new Map();

  const layoutedNodes = nodes.map((node, i) => {
    const label = node.id; // The unique ID from networkx (filepath, external::lib, file::func)
    const type = node.type || 'default'; // 'file', 'function', 'class', 'external'
    let folder = '.'; // Default for root files or non-file nodes

    // Determine folder for coloring:
    // Files: Use their parent directory.
    // Functions/Classes: Use their parent file's directory.
    // External: Use a dedicated key 'external'.
    let colorKey = '.'; // Key used to pick color from palette
    if (type === 'file') {
        if (label.includes('/')) {
            colorKey = label.substring(0, label.lastIndexOf('/'));
        }
    } else if (type === 'function' || type === 'class') {
        // Assume 'file' attribute exists on function/class nodes from backend data
        const parentFile = node.file;
        if (parentFile && parentFile.includes('/')) {
           colorKey = parentFile.substring(0, parentFile.lastIndexOf('/'));
        }
        // If no parent file info, default to root color
    } else if (type === 'external'){
        colorKey = 'external'; // Use a consistent key for all external nodes
    }

    // --- Assign color index and get color ---
    let colorIndex;
    if (folderColorMap.has(colorKey)) {
        colorIndex = folderColorMap.get(colorKey);
    } else {
        colorIndex = getFolderColorIndex(colorKey);
        folderColorMap.set(colorKey, colorIndex);
    }
    const nodeColor = COLOR_PALETTE[colorIndex % COLOR_PALETTE.length];
    // --- End Color Assignment ---

    // Base Style - common properties
    let style = {
      borderRadius: '8px',
      padding: '10px 15px',
      fontSize: '11px',
      minWidth: '150px',
      maxWidth: '220px',
      textAlign: 'center',
      wordBreak: 'break-word',
      border: '1px solid #6c757d', // Consistent medium-gray border
      boxShadow: '0 1px 3px rgba(0,0,0,0.08)', // Softer shadow
      color: '#1e293b', // Default dark text (slate-800)
    };

    // Style Adjustments by Type
    if (type === 'file') {
      style.background = nodeColor || '#e0f3ff'; // Folder color / fallback blue
    } else if (type === 'external') {
      style.background = '#dcfce7'; // Tailwind green-100
      style.border = '1px solid #4ade80'; // Tailwind green-400 border
      style.color = '#15803d';     // Tailwind green-800 text
    } else if (type === 'function' || type === 'class') {
      style.background = '#fffbeb'; // Tailwind amber-50
      style.border = '1px solid #fcd34d'; // Tailwind amber-300 border
      style.color = '#92400e';     // Tailwind amber-800 text
      style.padding = '8px 12px';
      style.borderRadius = '4px'; // Slightly different shape
    } else {
      style.background = '#f1f5f9'; // Tailwind slate-100 (default)
    }

    return {
      id: node.id,
      // Simple grid layout - consider using elkjs or dagre for auto-layout later if needed
      position: { x: (i % 8) * 250, y: Math.floor(i / 8) * 120 },
      data: { label: label, type: type }, // Pass label and type
      style: style,
    };
  });

  // Edge Styling
  const layoutedEdges = edges.map((edge, i) => {
      const isDefineEdge = edge.relationship === 'defines';
      const edgeColor = isDefineEdge ? '#f59e0b' : '#3b82f6'; // Amber (defines) vs Blue (imports)

      return {
        id: `e-${edge.source}-${edge.target}-${i}`, // Use index for potential multiple edges
        source: edge.source,
        target: edge.target,
        animated: !isDefineEdge, // Animate only import edges
        style: {
          stroke: edgeColor,
          strokeDasharray: isDefineEdge ? '4 4' : undefined, // Dashed for defines
          strokeWidth: isDefineEdge ? 1.2 : 1.8, // Thinner for defines
        },
        markerEnd: {
          type: 'arrowclosed',
          width: 15, height: 15,
          color: edgeColor // Match arrow color to line color
        },
        type: 'smoothstep', // Use smoothstep edges for potentially better routing
        // zIndex: isDefineEdge ? 0 : 1 // Optional: draw import lines above define lines
      };
  });


  return { layoutedNodes, layoutedEdges };
};

// --- MAIN GRAPH COMPONENT ---
export default function DependencyGraph({ graphData }) {
  // Memoize the layout calculation to avoid re-running on every render
  const { layoutedNodes, layoutedEdges } = useMemo(() => {
    // networkx format is { nodes: [...], links: [...] }
    const nodes = graphData?.nodes || [];
    const edges = graphData?.links || []; // Use 'links' as the key from networkx node_link_data
    return getLayoutedElements(nodes, edges);
  }, [graphData]); // Dependency array: only recompute when graphData changes

  // Handle cases where graph data might be missing or empty
  if (!graphData || !graphData.nodes || graphData.nodes.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-center p-10 bg-slate-50 rounded-lg">
        <div>
          <h3 className="font-semibold text-slate-700">No Graph Data Available</h3>
          <p className="text-sm text-slate-500 mt-1">
            {graphData === null
              ? "Graph generation may have failed or is not included in the analysis report."
              : "No nodes found in the dependency data."}
          </p>
        </div>
      </div>
    );
  }

  return (
    // Wrap ReactFlow in a div with defined height/width
    <div style={{ height: '100%', width: '100%' }}>
        <ReactFlow
          nodes={layoutedNodes}
          edges={layoutedEdges}
          fitView // Zooms/pans to fit all nodes initially
          nodesDraggable={true} // Allow nodes to be moved
          edgesFocusable={true} // Allow edge selection (useful for future features)
          minZoom={0.1} // Allow zooming out significantly
          // defaultViewport={{ x: 0, y: 0, zoom: 0.7 }} // Optional: Start slightly zoomed out
          proOptions={{ hideAttribution: true }} // Hides the React Flow attribution text
          // Consider adding event handlers (onNodeClick, onEdgeClick) later for interactivity
        >
          <MiniMap
              nodeStrokeWidth={3}
              zoomable pannable
              // Use node background color for minimap representation
              nodeColor={n => n.style?.background || '#eee'}
              style={{ backgroundColor: '#f8fafc' }} // Light background for minimap
          />
          <Controls /> {/* Adds zoom/pan controls */}
          <Background variant="dots" gap={16} size={0.5} /> {/* Adds a dotted background */}
        </ReactFlow>
    </div>
  );
}

