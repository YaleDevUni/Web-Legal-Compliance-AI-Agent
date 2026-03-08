import React, { useEffect, useState, useCallback, useRef, useMemo } from "react";
import ForceGraph2D from "react-force-graph-2d";
import type { ForceGraphMethods, NodeObject } from "react-force-graph-2d";

interface GraphNode extends NodeObject {
  id: string;
  name: string;
  law_name?: string;
  article_number?: string;
}

interface GraphLink {
  source: string;
  target: string;
}

interface LawGraphViewProps {
  citedArticleIds: string[]; // 현재 답변에서 인용된 조문 ID들
  onNodeClick?: (articleId: string) => void;
  width?: number;
  height?: number;
}

// React.memo를 사용하여 부모의 다른 상태(스트리밍 텍스트 등) 변화로 인한 불필요한 리렌더링 방지
const LawGraphView: React.FC<LawGraphViewProps> = React.memo(({ 
  citedArticleIds, 
  onNodeClick, 
  width = 600, 
  height = 400 
}) => {
  const [rawData, setRawData] = useState<{ nodes: GraphNode[]; links: GraphLink[] }>({ nodes: [], links: [] });
  const fgRef = useRef<ForceGraphMethods | undefined>(undefined);

  // 1. 컴포넌트 마운트 시에만 그래프 데이터 로드
  useEffect(() => {
    fetch("/api/graph")
      .then((res) => res.json())
      .then((json) => {
        setRawData(json);
      })
      .catch((err) => console.error("그래프 로드 실패:", err));
  }, []); // 의존성 배열을 비워 처음에만 실행

  // 2. 인용된 ID들을 Set으로 관리하여 검색 성능 최적화
  const citedSet = useMemo(() => new Set(citedArticleIds), [citedArticleIds]);

  const handleNodeClick = useCallback((node: any) => {
    const graphNode = node as GraphNode;
    if (onNodeClick && graphNode.id) {
      onNodeClick(graphNode.id);
    }
    
    if (fgRef.current && graphNode.x !== undefined && graphNode.y !== undefined) {
      fgRef.current.centerAt(graphNode.x, graphNode.y, 600);
      fgRef.current.zoom(2.5, 600);
    }
  }, [onNodeClick]);

  return (
    <div style={{ border: "1px solid #e2e8f0", borderRadius: "12px", overflow: "hidden", background: "#f8fafc" }}>
      <ForceGraph2D
        ref={fgRef}
        graphData={rawData}
        width={width}
        height={height}
        nodeLabel="name"
        // 3. 데이터를 다시 불러오지 않고 렌더링 시점에 색상 결정
        nodeColor={(node: any) => citedSet.has((node as GraphNode).id) ? "#ef4444" : "#3b82f6"}
        nodeRelSize={4}
        // 4. 인용된 노드는 크기를 더 크게 표시
        nodeVal={(node: any) => citedSet.has((node as GraphNode).id) ? 3 : 1}
        linkDirectionalArrowLength={3}
        linkDirectionalArrowRelPos={1}
        linkColor={() => "#cbd5e1"}
        onNodeClick={handleNodeClick}
        cooldownTicks={50} // 물리 엔진 계산 시간 단축
      />
    </div>
  );
});

export default LawGraphView;
