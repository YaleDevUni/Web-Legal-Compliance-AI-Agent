import React, { useCallback, useRef, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import ForceGraph2D from "react-force-graph-2d";
import type { ForceGraphMethods, NodeObject } from "react-force-graph-2d";

interface GraphNode extends NodeObject {
  id: string;
  name: string;
  law_name?: string;
  article_number?: string;
}

interface GraphLink {
  source: string | { id: string };
  target: string | { id: string };
}

interface LawGraphViewProps {
  citedArticleIds: string[]; // 직접 인용된 조문 ID
  relatedArticleIds?: string[]; // 그래프 확장을 통해 연관된 조문 ID
  onNodeClick?: (articleId: string) => void;
  width?: number;
  height?: number;
}

const LawGraphView: React.FC<LawGraphViewProps> = React.memo(({ 
  citedArticleIds, 
  relatedArticleIds = [],
  onNodeClick, 
  width = 600, 
  height = 400 
}) => {
  const fgRef = useRef<ForceGraphMethods | undefined>(undefined);

  // 전체 그래프 데이터 캐싱 (한 번만 로드)
  const { data: fullGraph } = useQuery({
    queryKey: ["law-graph"],
    queryFn: async () => {
      const res = await fetch("/api/graph");
      if (!res.ok) throw new Error("그래프 로드 실패");
      return res.json() as Promise<{ nodes: GraphNode[]; links: GraphLink[] }>;
    },
    staleTime: Infinity,
  });

  // 현재 인용/연관된 조문들만 필터링하여 서브그래프 생성
  const subGraphData = useMemo(() => {
    if (!fullGraph) return { nodes: [], links: [] };

    const visibleIds = new Set([...citedArticleIds, ...relatedArticleIds]);
    if (visibleIds.size === 0) return { nodes: [], links: [] };

    // 1. 노드 필터링
    const filteredNodes = fullGraph.nodes.filter(node => visibleIds.has(node.id));

    // 2. 엣지 필터링 (양쪽 노드가 모두 가시권에 있는 경우만)
    const filteredLinks = fullGraph.links.filter(link => {
      const sourceId = typeof link.source === 'string' ? link.source : (link.source as any).id;
      const targetId = typeof link.target === 'string' ? link.target : (link.target as any).id;
      return visibleIds.has(sourceId) && visibleIds.has(targetId);
    });

    return { nodes: filteredNodes, links: filteredLinks };
  }, [fullGraph, citedArticleIds, relatedArticleIds]);

  const handleNodeClick = useCallback((node: any) => {
    const graphNode = node as GraphNode;
    if (onNodeClick && graphNode.id) {
      onNodeClick(graphNode.id);
    }
  }, [onNodeClick]);

  if (!fullGraph || subGraphData.nodes.length === 0) {
    return (
      <div style={{ width, height, display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#f8fafc', color: '#94a3b8', fontSize: '10px' }}>
        {citedArticleIds.length === 0 ? "인용된 조문이 여기에 표시됩니다." : "그래프 생성 중..."}
      </div>
    );
  }

  return (
    <div style={{ border: "1px solid #e2e8f0", borderRadius: "12px", overflow: "hidden", background: "#f8fafc" }}>
      <ForceGraph2D
        ref={fgRef}
        graphData={subGraphData}
        width={width}
        height={height}
        nodeLabel="name"
        nodeColor={(node: any) => citedArticleIds.includes((node as GraphNode).id) ? "#ef4444" : "#fbbf24"}
        nodeRelSize={6}
        nodeVal={(node: any) => citedArticleIds.includes((node as GraphNode).id) ? 2 : 1}
        linkDirectionalArrowLength={4}
        linkDirectionalArrowRelPos={1}
        linkColor={() => "#94a3b8"}
        linkWidth={1.5}
        onNodeClick={handleNodeClick}
        // 노드가 적으므로 더 활발한 물리 엔진 설정
        d3AlphaDecay={0.02}
        d3VelocityDecay={0.3}
        cooldownTicks={100}
      />
    </div>
  );
});

export default LawGraphView;
