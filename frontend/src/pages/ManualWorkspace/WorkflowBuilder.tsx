import { useMemo, useState } from 'react';
import {
  Button,
  Card,
  Divider,
  Empty,
  Form,
  Input,
  List,
  Select,
  Space,
  Switch,
  Tag,
  Typography,
} from 'antd';
import {
  ArrowDownOutlined,
  ArrowUpOutlined,
  BranchesOutlined,
  DeleteOutlined,
  PlusOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { workspaceModuleCatalog } from '../../data/moduleCatalog';
import { familyDisplayName, moduleDisplayName, useI18n } from '../../i18n';
import { useTaskStore } from '../../stores';
import type { WorkflowBlueprint, WorkflowEdgeConfig, WorkflowNodeConfig, WorkspaceModule } from '../../types';

interface WorkflowBuilderProps {
  selectedModuleId?: string;
}

const defaultProvider = 'local';

function WorkflowBuilder({ selectedModuleId }: WorkflowBuilderProps) {
  const [blueprintName, setBlueprintName] = useState('');
  const [nodes, setNodes] = useState<WorkflowNodeConfig[]>([]);
  const { language, t } = useI18n();
  const startTask = useTaskStore((state) => state.startTask);
  const runDemoProgress = useTaskStore((state) => state.runDemoProgress);
  const addReviewItem = useTaskStore((state) => state.addReviewItem);

  const edges = useMemo(() => buildSequentialEdges(nodes), [nodes]);
  const selectedModule = workspaceModuleCatalog.find((item) => item.id === selectedModuleId);
  const effectiveBlueprintName = blueprintName || t('defaultWorkflowName');
  const blueprint = useMemo(
    () => buildBlueprint(effectiveBlueprintName, nodes, edges, t('blueprintDescription')),
    [effectiveBlueprintName, nodes, edges, t],
  );

  const addModule = (module: WorkspaceModule) => {
    setNodes((current) => [...current, createNode(module, current.length, language)]);
  };

  const moveNode = (id: string, direction: -1 | 1) => {
    setNodes((current) => {
      const index = current.findIndex((node) => node.id === id);
      const nextIndex = index + direction;
      if (index < 0 || nextIndex < 0 || nextIndex >= current.length) {
        return current;
      }
      const next = [...current];
      [next[index], next[nextIndex]] = [next[nextIndex], next[index]];
      return next;
    });
  };

  const updateNode = (id: string, updates: Partial<WorkflowNodeConfig>) => {
    setNodes((current) => current.map((node) => (node.id === id ? { ...node, ...updates } : node)));
  };

  const runBlueprint = () => {
    const id = startTask({
      title: `${effectiveBlueprintName} - ${t('freeWorkflow')}`,
      kind: 'workflow',
      mode: 'manual',
      backend: 'workflow_blueprint',
      provider: 'workspace',
      stage: localizedBlueprintStages(language)[0],
    });
    addReviewItem(id, {
      title:
        language === 'en-US'
          ? 'Review custom workflow node bindings'
          : language === 'ja-JP'
            ? 'カスタムworkflowノードのバインドを確認'
            : '复核自定义工作流节点绑定',
      priority: 'high',
      status: 'open',
      summary:
        language === 'en-US'
          ? 'Confirm each node input binding, output path, backend/provider, and human review gate.'
          : language === 'ja-JP'
            ? '各ノードの入力バインド、出力先、backend/provider、人間レビューゲートを確認します。'
            : '确认每个节点的输入绑定、输出路径、backend/provider 和人工复核门槛。',
    });
    runDemoProgress(id, [localizedBlueprintStages(language)[1], ...nodes.map((node) => node.label), ...localizedBlueprintStages(language).slice(2)]);
  };

  const addSelectedModule = () => {
    if (selectedModule) {
      addModule(selectedModule);
    }
  };

  return (
    <div className="workbench-grid">
      <Card
        title={
          <Space>
            <BranchesOutlined />
            {t('freeWorkflow')}
          </Space>
        }
        extra={
          <Button disabled={!selectedModule} icon={<PlusOutlined />} onClick={addSelectedModule}>
            {t('addCurrentModule')}
          </Button>
        }
      >
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          <Input
            addonBefore={t('workflowName')}
            onChange={(event) => setBlueprintName(event.target.value)}
            value={blueprintName || t('defaultWorkflowName')}
          />
          <Space wrap>
            {workspaceModuleCatalog.slice(0, 12).map((module) => (
              <Button key={module.id} onClick={() => addModule(module)} size="small">
                {moduleDisplayName(module, language)}
              </Button>
            ))}
          </Space>
          <Divider style={{ margin: '8px 0' }} />
          {nodes.length === 0 ? (
            <Empty description={t('addNodesHint')} />
          ) : (
            <List
              dataSource={nodes}
              renderItem={(node, index) => (
                <List.Item>
                  <NodeEditor
                    index={index}
                    node={node}
                    onMove={moveNode}
                    onRemove={(id) => setNodes((current) => current.filter((item) => item.id !== id))}
                    onUpdate={updateNode}
                  />
                </List.Item>
              )}
            />
          )}
          <Button block disabled={nodes.length === 0} icon={<ThunderboltOutlined />} onClick={runBlueprint} type="primary">
            {t('runBlueprint')}
          </Button>
        </Space>
      </Card>

      <Space direction="vertical" size={16}>
        <Card title={t('nodeConnections')}>
          {edges.length === 0 ? (
            <Typography.Text className="muted">
              {language === 'en-US'
                ? 'Add two or more nodes to form sequential links. Input and output bindings stay editable inside each node.'
                : language === 'ja-JP'
                  ? '2つ以上のノードを追加すると順序接続が作られます。入出力バインドは各ノードで編集できます。'
                  : '添加两个以上节点后自动形成顺序连接，可在节点配置中修改输入输出绑定。'}
            </Typography.Text>
          ) : (
            <List
              dataSource={edges}
              renderItem={(edge) => (
                <List.Item>
                  <Typography.Text>
                    {labelForNode(nodes, edge.from)} → {labelForNode(nodes, edge.to)}
                  </Typography.Text>
                  <Tag>{edge.outputKey} → {edge.inputKey}</Tag>
                </List.Item>
              )}
            />
          )}
        </Card>
        <Card title={t('blueprintJson')}>
          <pre className="task-log">{JSON.stringify(blueprint, null, 2)}</pre>
        </Card>
      </Space>
    </div>
  );
}

function NodeEditor({
  index,
  node,
  onMove,
  onRemove,
  onUpdate,
}: {
  index: number;
  node: WorkflowNodeConfig;
  onMove: (id: string, direction: -1 | 1) => void;
  onRemove: (id: string) => void;
  onUpdate: (id: string, updates: Partial<WorkflowNodeConfig>) => void;
}) {
  const { language, t } = useI18n();
  const module = workspaceModuleCatalog.find((item) => item.id === node.moduleId);

  return (
    <Card size="small" style={{ width: '100%' }} title={`${index + 1}. ${node.label}`}>
      <Form layout="vertical">
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          <Space wrap>
            {module && <Tag color="blue">{familyDisplayName(module.family, language)}</Tag>}
            <Tag>{module?.executionTarget}</Tag>
            {module?.privacy !== 'local_first' && <Tag color="warning">{module?.privacy}</Tag>}
          </Space>
          <Form.Item label={t('nodeName')}>
            <Input value={node.label} onChange={(event) => onUpdate(node.id, { label: event.target.value })} />
          </Form.Item>
          <Form.Item label={`${t('input')} binding`}>
            <Input value={node.inputBinding} onChange={(event) => onUpdate(node.id, { inputBinding: event.target.value })} />
          </Form.Item>
          <Form.Item label={t('outputLocation')}>
            <Input value={node.outputBinding} onChange={(event) => onUpdate(node.id, { outputBinding: event.target.value })} />
          </Form.Item>
          <Space wrap>
            <Select
              style={{ minWidth: 140 }}
              value={node.backend}
              options={(module?.backends ?? ['script']).map((value) => ({ label: value, value }))}
              onChange={(backend) => onUpdate(node.id, { backend })}
            />
            <Input
              addonBefore="provider"
              style={{ width: 220 }}
              value={node.provider}
              onChange={(event) => onUpdate(node.id, { provider: event.target.value })}
            />
            <Switch
              checked={node.reviewGate}
              checkedChildren={t('needsReview')}
              unCheckedChildren={t('unchecked')}
              onChange={(reviewGate) => onUpdate(node.id, { reviewGate })}
            />
          </Space>
          <Space>
            <Button icon={<ArrowUpOutlined />} onClick={() => onMove(node.id, -1)} size="small" />
            <Button icon={<ArrowDownOutlined />} onClick={() => onMove(node.id, 1)} size="small" />
            <Button danger icon={<DeleteOutlined />} onClick={() => onRemove(node.id)} size="small">
              {t('delete')}
            </Button>
          </Space>
        </Space>
      </Form>
    </Card>
  );
}

function createNode(module: WorkspaceModule, index: number, language: ReturnType<typeof useI18n>['language']): WorkflowNodeConfig {
  return {
    id: `node-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    moduleId: module.id,
    label: moduleDisplayName(module, language),
    inputBinding: index === 0 ? 'workspace.input' : `nodes.${index}.output`,
    outputBinding: `artifacts.${module.taskType}`,
    backend: module.backends[0] ?? 'script',
    provider: defaultProvider,
    preset: module.presets?.[0],
    reviewGate: module.reviewRequired,
    enabled: true,
  };
}

function buildSequentialEdges(nodes: WorkflowNodeConfig[]): WorkflowEdgeConfig[] {
  return nodes.slice(1).map((node, index) => ({
    id: `edge-${nodes[index].id}-${node.id}`,
    from: nodes[index].id,
    to: node.id,
    outputKey: nodes[index].outputBinding,
    inputKey: node.inputBinding,
  }));
}

function buildBlueprint(
  name: string,
  nodes: WorkflowNodeConfig[],
  edges: WorkflowEdgeConfig[],
  description: string,
): WorkflowBlueprint {
  const now = Date.now();
  return {
    id: 'manual-blueprint-preview',
    name,
    description,
    nodes,
    edges,
    createdAt: now,
    updatedAt: now,
  };
}

function localizedBlueprintStages(language: ReturnType<typeof useI18n>['language']) {
  if (language === 'en-US') {
    return ['Prepare node graph', 'Parse blueprint', 'Register package', 'Generate workflow handoff'];
  }
  if (language === 'ja-JP') {
    return ['ノード図を準備', 'blueprintを解析', 'packageを登録', 'workflow引き継ぎを生成'];
  }
  return ['准备节点图', '解析蓝图', '登记 package', '生成 workflow handoff'];
}

function labelForNode(nodes: WorkflowNodeConfig[], id: string) {
  return nodes.find((node) => node.id === id)?.label ?? id;
}

export default WorkflowBuilder;
