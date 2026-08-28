import { useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Send,
  Square,
  Plus,
  Bot,
  User,
  ChevronDown,
  ChevronRight,
  Wrench,
  Brain,
  Zap,
  Shield,
  GitBranch,
  MessageSquare,
  BarChart3,
  FileCheck,
  AlertTriangle,
  Clock,
  Check,
  X,
  Sparkles,
  Loader2,
  ArrowRight,
  Lightbulb,
  Target,
} from 'lucide-react';
import { sendChatMessage, type OntologyMeta } from '../services/stream';
import { useAppStore } from '../store';
import type { Message, Intent, RoutingInfo, ToolUsage, ReasoningTrace, ReasoningStep } from '../types';
import ReasoningPanel from '../components/ai/ReasoningPanel';

interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  level: number;
  createdAt: string;
}

const STORAGE_KEY = 'ai-finance-conversations';

function loadConversations(): Conversation[] {
  try {
    const data = localStorage.getItem(STORAGE_KEY);
    if (data) return JSON.parse(data);
  } catch { /* ignore */ }
  return [];
}

function saveConversations(conversations: Conversation[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
  } catch { /* ignore */ }
}

const SUGGESTED_PROMPTS = [
  '查看B2研发支出执行率',
  '津康Q2招待费用率为什么偏离？',
  '帮我分析B5市场推广3GAP',
  '如果把发展象限50万调到收缩象限？',
];

// v10.0: 6 级 LEVEL 颜色统一为 2 色（L1-3 蓝，L4-6 深蓝）
const LEVEL_CONFIG: Record<number, { label: string; color: string; bg: string; icon: typeof Zap }> = {
  1: { label: 'L1 问答', color: 'text-brand-700', bg: 'bg-brand-50 border-brand-200', icon: MessageSquare },
  2: { label: 'L2 查询', color: 'text-brand-700', bg: 'bg-brand-50 border-brand-200', icon: BarChart3 },
  3: { label: 'L3 分析', color: 'text-brand-700', bg: 'bg-brand-50 border-brand-200', icon: Brain },
  4: { label: 'L4 推理', color: 'text-finance-700', bg: 'bg-finance-50 border-finance-200', icon: GitBranch },
  5: { label: 'L5 决策', color: 'text-finance-700', bg: 'bg-finance-50 border-finance-200', icon: Shield },
  6: { label: 'L6 执行', color: 'text-finance-700', bg: 'bg-finance-50 border-finance-200', icon: FileCheck },
};

// v10.0: 规则匹配 badge 统一为中性灰
const RULE_TYPE_STYLE: Record<string, { badge: string; color: string }> = {
  hard: { badge: 'badge-gray', color: 'text-surface-700' },
  soft: { badge: 'badge-gray', color: 'text-surface-700' },
  reasoning: { badge: 'badge-gray', color: 'text-surface-700' },
};

const OUTPUT_STYLE: Record<string, string> = {
  PASS: 'bg-compliance-50 text-compliance-700 border-compliance-200',
  BLOCK: 'bg-alert-50 text-alert-700 border-alert-200',
  WARNING: 'bg-warning-50 text-warning-700 border-warning-200',
};

// ─── AI Work Process Timeline ──────────────────────────────────────────────

function WorkTimeline({ steps }: { steps: { label: string; status: 'done' | 'active' | 'pending'; detail?: string }[] }) {
  return (
    <div className="flex items-center gap-0 mb-4">
      {steps.map((step, i) => (
        <motion.div
          key={i}
          className="flex items-center"
          initial={{ opacity: 0.3, scale: 0.9 }}
          animate={{
            opacity: step.status === 'pending' ? 0.3 : 1,
            scale: 1,
          }}
          transition={{ duration: 0.2 }}
        >
          <div className="flex flex-col items-center">
            <div className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold transition-all duration-300 ${
              step.status === 'done' ? 'bg-compliance-500 text-white' :
              step.status === 'active' ? 'bg-brand-500 text-white animate-pulse' :
              'bg-surface-100 text-surface-400'
            }`}>
              {step.status === 'done' ? <Check size={10} /> :
               step.status === 'active' ? <Loader2 size={10} className="animate-spin" /> :
               i + 1}
            </div>
            <span className={`text-[9px] mt-0.5 whitespace-nowrap ${
              step.status === 'done' ? 'text-compliance-600' :
              step.status === 'active' ? 'text-brand-600 font-medium' :
              'text-surface-400'
            }`}>
              {step.label}
            </span>
            {step.detail && step.status === 'done' && (
              <span className="text-[8px] text-surface-400 mt-0.5">{step.detail}</span>
            )}
          </div>
          {i < steps.length - 1 && (
            <div className={`w-6 h-px mx-1 transition-all duration-300 ${
              step.status === 'done' ? 'bg-compliance-300' : 'bg-surface-200'
            }`} />
          )}
        </motion.div>
      ))}
    </div>
  );
}

// ─── Action Card (AI建议可执行) ────────────────────────────────────────────

function ActionCard({ action, index }: { action: { label: string; description?: string; type: 'primary' | 'secondary' | 'danger' }; index: number }) {
  const [executed, setExecuted] = useState(false);
  const typeConfig = {
    primary: { bg: 'bg-brand-500 hover:bg-brand-600', text: 'text-white', border: '' },
    secondary: { bg: 'bg-white hover:bg-surface-50', text: 'text-surface-700', border: 'border border-surface-200' },
    danger: { bg: 'bg-alert-500 hover:bg-alert-600', text: 'text-white', border: '' },
  };
  const config = typeConfig[action.type];

  if (executed) {
    return (
      <motion.div
        initial={{ scale: 0.95 }}
        animate={{ scale: 1 }}
        className="flex items-center gap-2 px-3 py-2 rounded-lg bg-compliance-50 border border-compliance-200"
      >
        <Check size={12} className="text-compliance-500" />
        <span className="text-xs text-compliance-700">已执行: {action.label}</span>
      </motion.div>
    );
  }

  return (
    <motion.button
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      whileHover={{ y: -1 }}
      whileTap={{ scale: 0.98 }}
      onClick={() => setExecuted(true)}
      className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-all duration-150 shadow-sm ${config.bg} ${config.text} ${config.border}`}
    >
      <Lightbulb size={12} className={action.type === 'primary' ? 'text-white' : 'text-brand-500'} />
      <span>{action.label}</span>
      {action.description && <span className="opacity-60 text-[10px]">{action.description}</span>}
      <ArrowRight size={10} className="ml-auto opacity-40" />
    </motion.button>
  );
}

// ─── Thinking Dots ─────────────────────────────────────────────────────────

function ThinkingDots() {
  return (
    <div className="flex items-center gap-1 px-3 py-2">
      {[0, 1, 2].map((i) => (
        <motion.div
          key={i}
          className="w-2 h-2 rounded-full bg-finance-400"
          animate={{ opacity: [0.3, 1, 0.3], scale: [0.85, 1.1, 0.85] }}
          transition={{ duration: 1.2, repeat: Infinity }}
        />
      ))}
      <span className="ml-2 text-xs text-surface-400">AI 正在分析...</span>
    </div>
  );
}

// ─── Intent Badge ─────────────────────────────────────────────────────────

function IntentBadge({ intent }: { intent: Intent }) {
  return (
    <motion.span
      initial={{ opacity: 0, scale: 0.8 }}
      animate={{ opacity: 1, scale: 1 }}
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-finance-50 text-finance-700 border border-finance-200"
    >
      <Target size={10} />
      场景识别: {intent.primary}
      {intent.confidence > 0 && (
        <span className="ml-0.5 opacity-60">({Math.round(intent.confidence * 100)}%)</span>
      )}
    </motion.span>
  );
}

// ─── Routing Badge ────────────────────────────────────────────────────────

function RoutingBadge({ routing }: { routing: RoutingInfo }) {
  return (
    <motion.span
      initial={{ opacity: 0, scale: 0.8 }}
      animate={{ opacity: 1, scale: 1 }}
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-purple-50 text-purple-700 border border-purple-200"
    >
      <Sparkles size={10} />
      AI: {routing.agent_name}
      {routing.skill_id && <span className="opacity-60">/{routing.skill_id}</span>}
    </motion.span>
  );
}

// ─── Tool Usage Section ───────────────────────────────────────────────────

function ToolUsageSection({ tools }: { tools: ToolUsage[] }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="mt-3">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1.5 text-xs text-surface-500 hover:text-surface-700 transition-colors"
      >
        {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        <Wrench size={12} />
        <span>AI 调用了 {tools.length} 个工具</span>
        {tools.some(t => t.data_fetched) && (
          <span className="text-[10px] text-finance-500 font-medium ml-1">
            · 获取 {tools.filter(t => t.data_fetched).reduce((sum, t) => sum + (t.data_fetched || 0), 0)} 条数据
          </span>
        )}
      </button>
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="mt-2 space-y-2">
              {tools.map((tool, i) => (
                <div
                  key={i}
                  className="p-2.5 rounded-lg bg-surface-50 border border-surface-200/60 text-xs"
                >
                  <div className="flex items-center gap-2 mb-1">
                    <Wrench size={10} className="text-surface-400" />
                    <span className="font-medium text-surface-700">{tool.tool_name}</span>
                    {tool.data_fetched && (
                      <span className="px-1.5 py-0.5 rounded text-[10px] bg-finance-50 text-finance-600 font-medium">
                        {tool.data_fetched} 条数据
                      </span>
                    )}
                    {tool.tables_queried && tool.tables_queried.length > 0 && (
                      <span className="text-[10px] text-surface-400">
                        来源: {tool.tables_queried.join(', ')}
                      </span>
                    )}
                    <span className="text-surface-400 ml-auto flex items-center gap-1">
                      <Clock size={8} />
                      {tool.execution_time_ms}ms
                    </span>
                  </div>
                  <div className="font-mono text-[10px] text-surface-500 bg-white rounded p-1.5 border border-surface-100 whitespace-pre-wrap max-h-24 overflow-y-auto">
                    {tool.tool_output}
                  </div>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ─── Reasoning Trace Section ──────────────────────────────────────────────

function ReasoningTraceSection({ trace }: { trace: ReasoningTrace }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="mt-3">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1.5 text-xs text-surface-500 hover:text-surface-700 transition-colors"
      >
        {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        <Brain size={12} />
        <span>AI 推理链路 ({trace.steps.length}步 · {trace.total_time_ms}ms)</span>
      </button>
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="mt-2 space-y-2">
              {trace.steps.map((step, i) => (
                <ReasoningStepCard key={step.step_id} step={step} index={i} />
              ))}
              <div className="p-2.5 rounded-lg bg-finance-50 border border-finance-200">
                <div className="flex items-center gap-1.5 mb-1">
                  <Lightbulb size={10} className="text-finance-600" />
                  <span className="text-xs font-semibold text-finance-800">推理结论</span>
                </div>
                <p className="text-xs text-finance-700">{trace.conclusion}</p>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ─── Reasoning Step Card ──────────────────────────────────────────────────

function ReasoningStepCard({ step, index }: { step: ReasoningStep; index: number }) {
  const ruleStyle = step.rule_type ? RULE_TYPE_STYLE[step.rule_type] : null;
  const outputStyle = OUTPUT_STYLE[step.output] || 'bg-surface-50 text-surface-700 border-surface-200';

  return (
    <div className="p-2.5 rounded-lg bg-white border border-surface-200/60">
      <div className="flex items-center gap-2 mb-1.5">
        <span className="flex items-center justify-center w-5 h-5 rounded-full bg-surface-100 text-[10px] font-bold text-surface-600">
          {index + 1}
        </span>
        {step.rule_id && (
          <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${ruleStyle?.badge || 'badge-purple'}`}>
            {step.rule_id}
          </span>
        )}
        {step.rule_type && (
          <span className={`text-[10px] font-medium ${ruleStyle?.color || 'text-surface-500'}`}>
            {step.rule_type === 'hard' ? '硬规则' : step.rule_type === 'soft' ? '软规则' : '推理规则'}
          </span>
        )}
        <span className="ml-auto text-[10px] text-surface-400 flex items-center gap-1">
          <Clock size={8} />
          {step.duration_ms}ms
        </span>
      </div>
      <p className="text-xs text-surface-600 mb-1.5">{step.description}</p>
      <div className="flex items-center gap-2">
        <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold border ${outputStyle}`}>
          {step.output}
        </span>
        <div className="flex-1 h-1.5 bg-surface-100 rounded-full overflow-hidden">
          <motion.div
            className="h-full rounded-full bg-finance-500"
            initial={{ width: 0 }}
            animate={{ width: `${step.confidence * 100}%` }}
            transition={{ duration: 0.5 }}
          />
        </div>
        <span className="text-[10px] text-surface-400 font-mono">
          {Math.round(step.confidence * 100)}%
        </span>
      </div>
    </div>
  );
}

// ─── Message Bubble (AI Work Space Mode) ──────────────────────────────────

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user';
  const [showAnalysis, setShowAnalysis] = useState(false);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}
    >
      <div
        className={`flex-shrink-0 w-9 h-9 rounded-xl flex items-center justify-center ${
          isUser
            ? 'bg-gradient-to-br from-brand-400 to-finance-600'
            : 'bg-gradient-to-br from-finance-500 to-finance-700'
        }`}
      >
        {isUser ? <User size={15} className="text-white" /> : <Bot size={15} className="text-white" />}
      </div>

      <div className={`max-w-[78%] ${isUser ? 'items-end' : 'items-start'}`}>
        {!isUser && (message.intent || message.routing) && (
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex flex-wrap items-center gap-1.5 mb-2"
          >
            {message.intent && <IntentBadge intent={message.intent} />}
            {message.routing && <RoutingBadge routing={message.routing} />}
          </motion.div>
        )}

        <div
          className={`rounded-2xl px-4 py-3 ${
            isUser
              ? 'bg-finance-50 text-finance-900 rounded-tr-sm'
              : 'bg-white border border-surface-200/60 text-surface-800 rounded-tl-sm shadow-sm'
          }`}
        >
          {isUser ? (
            <p className="text-sm whitespace-pre-wrap">{message.content}</p>
          ) : (
            <>
              {message.isStreaming && !message.content ? (
                <ThinkingDots />
              ) : (
                <>
                  {/* AI 分析过程 */}
                  {(message.tools_used || message.reasoning_trace) && (
                    <div className="mb-3 pb-3 border-b border-surface-100">
                      <WorkTimeline steps={[
                        { label: '理解意图', status: message.intent ? 'done' : 'pending' },
                        { label: '选择技能', status: message.routing ? 'done' : 'pending' },
                        { label: '获取数据', status: message.tools_used?.length ? 'done' : 'pending' },
                        { label: '分析推理', status: message.reasoning_trace ? 'done' : 'pending' },
                        { label: '生成回复', status: message.isStreaming ? 'active' : 'done' },
                      ]} />
                    </div>
                  )}

                  {/* AI 回复内容 */}
                  <div className="whitespace-pre-wrap text-sm leading-relaxed">
                    {typeof message.content === 'string' ? message.content : String(message.content || '')}
                  </div>
                </>
              )}
            </>
          )}
        </div>

        {/* AI 推理链路（本体） */}
        {!isUser && message.ontology && (
          <ReasoningPanel meta={message.ontology} />
        )}

        {/* AI 工具调用 */}
        {!isUser && message.tools_used && message.tools_used.length > 0 && (
          <ToolUsageSection tools={message.tools_used} />
        )}

        {/* AI 推理链路 */}
        {!isUser && message.reasoning_trace && (
          <ReasoningTraceSection trace={message.reasoning_trace} />
        )}

        {/* AI 建议（可执行） */}
        {!isUser && message.suggestions && message.suggestions.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-3"
          >
            <div className="flex items-center gap-1.5 mb-2">
              <Sparkles size={12} className="text-brand-500" />
              <span className="text-xs font-semibold text-surface-600">AI 建议</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {message.suggestions.map((s, i) => (
                <ActionCard
                  key={i}
                  index={i}
                  action={{ label: s, type: i === 0 ? 'primary' : 'secondary' }}
                />
              ))}
            </div>
          </motion.div>
        )}
      </div>
    </motion.div>
  );
}

// ─── Level Indicator ──────────────────────────────────────────────────────

function LevelIndicator({ level }: { level: number }) {
  return (
    <div className="space-y-1.5">
      {Array.from({ length: 6 }, (_, i) => {
        const lvl = i + 1;
        const config = LEVEL_CONFIG[lvl];
        const active = lvl <= level;
        const Icon = config.icon;

        return (
          <div
            key={lvl}
            className={`flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs transition-all duration-200 ${
              active
                ? `${config.bg} border ${config.color} font-semibold`
                : 'text-surface-300 bg-transparent'
            }`}
          >
            <Icon size={12} />
            <span>{config.label}</span>
          </div>
        );
      })}
    </div>
  );
}

// ─── Main Chat Page ───────────────────────────────────────────────────────

export default function ChatPage() {
  const { messages, setMessages, addMessage, updateMessage, setCurrentSessionId } = useAppStore();
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [conversations, setConversations] = useState<Conversation[]>(() => {
    const saved = loadConversations();
    return saved.length > 0 ? saved : [
      {
        id: 'conv-1',
        title: '新对话',
        messages: [],
        level: 1,
        createdAt: new Date().toISOString(),
      },
    ];
  });
  const [activeConvId, setActiveConvId] = useState<string>(() => {
    const saved = loadConversations();
    return saved.length > 0 ? saved[0].id : 'conv-1';
  });
  const [showSidebar, setShowSidebar] = useState(true);
  const abortRef = useRef<AbortController | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Save conversations to localStorage whenever they change
  useEffect(() => {
    saveConversations(conversations);
  }, [conversations]);

  // Restore messages from the active conversation on conversation change only
  useEffect(() => {
    const conv = conversations.find(c => c.id === activeConvId);
    if (conv && conv.messages.length > 0) {
      setMessages(conv.messages);
    } else {
      setMessages([]);
    }
  }, [activeConvId]);

  const activeConv = conversations.find((c) => c.id === activeConvId);
  const currentLevel = activeConv?.level || 1;

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  useEffect(() => {
    if (!isStreaming) {
      inputRef.current?.focus();
    }
  }, [isStreaming]);

  const handleSend = useCallback(
    (text?: string) => {
      const content = (text || input).trim();
      if (!content || isStreaming) return;

      const userMsg: Message = {
        id: crypto.randomUUID(),
        role: 'user',
        content,
        timestamp: new Date().toISOString(),
      };

      const assistantId = crypto.randomUUID();
      const assistantMsg: Message = {
        id: assistantId,
        role: 'assistant',
        content: '',
        timestamp: new Date().toISOString(),
        isStreaming: true,
      };

      addMessage(userMsg);
      addMessage(assistantMsg);
      setInput('');
      setIsStreaming(true);

      // Save user message to conversation and auto-generate title
      setConversations((prev) => {
        const updated = prev.map((conv) => {
          if (conv.id === activeConvId) {
            const newTitle = conv.title === '新对话' ? content.slice(0, 20) : conv.title;
            return { ...conv, title: newTitle, messages: [...conv.messages, userMsg, assistantMsg] };
          }
          return conv;
        });
        return updated;
      });

      const controller = new AbortController();
      abortRef.current = controller;

      // Build page context based on current location
      const pageContext: Record<string, string> = {};
      const pathname = window.location.pathname;
      if (pathname.includes('/budget')) pageContext.page = 'budget';
      else if (pathname.includes('/alerts')) pageContext.page = 'alerts';
      else if (pathname.includes('/expenses')) pageContext.page = 'expenses';
      else if (pathname.includes('/approvals')) pageContext.page = 'approvals';
      else if (pathname.includes('/analysis')) pageContext.page = 'analysis';

      sendChatMessage(
        content,
        {
          onThinking: () => {
            updateMessage(assistantId, { isStreaming: true });
          },
          onIntent: (data) => {
            updateMessage(assistantId, {
              intent: { primary: data.intent, confidence: data.confidence, scene_id: data.scene_id },
            });
          },
          onRouting: (data) => {
            updateMessage(assistantId, {
              routing: { agent_id: data.agent, agent_name: data.agent, routing_reason: data.intent },
            });
          },
          onOntology: (data: OntologyMeta) => {
            updateMessage(assistantId, { ontology: data });
          },
          onContent: (data) => {
            if (!data.chunk) return;
            const currentMessages = useAppStore.getState().messages;
            const current = currentMessages.find((m) => m.id === assistantId);
            updateMessage(assistantId, { content: (current?.content || '') + data.chunk });
          },
          onToolsUsed: (data) => {
            const tools: ToolUsage[] = (data.tools || []).map((name: string) => ({
              tool_name: name,
              tool_input: '',
              tool_output: '',
              execution_time_ms: 0,
            }));
            updateMessage(assistantId, { tools_used: tools });
          },
          onSuggestions: (data) => {
            updateMessage(assistantId, { suggestions: data.suggestions || [] });
          },
          onDone: () => {
            updateMessage(assistantId, { isStreaming: false });
            setIsStreaming(false);
            abortRef.current = null;
            // Save final assistant message to conversation
            const finalMessages = useAppStore.getState().messages;
            setConversations((prev) =>
              prev.map((conv) =>
                conv.id === activeConvId ? { ...conv, messages: finalMessages } : conv
              )
            );
          },
          onError: (data) => {
            const currentMessages = useAppStore.getState().messages;
            const current = currentMessages.find((m) => m.id === assistantId);
            updateMessage(assistantId, {
              content: (current?.content || '') + `\n\n⚠️ 错误: ${data.message}`,
              isStreaming: false,
            });
            setIsStreaming(false);
            abortRef.current = null;
          },
        },
        controller.signal,
        activeConvId,
        pageContext
      );
    },
    [input, isStreaming, addMessage, updateMessage, activeConvId]
  );

  const handleAbort = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
      setIsStreaming(false);
    }
  }, []);

  const handleNewConversation = useCallback(() => {
    const newConv: Conversation = {
      id: crypto.randomUUID(),
      title: '新对话',
      messages: [],
      level: 1,
      createdAt: new Date().toISOString(),
    };
    // Save current messages to current conversation before switching
    setConversations((prev) =>
      prev.map((conv) =>
        conv.id === activeConvId ? { ...conv, messages } : conv
      ).concat([newConv])
    );
    setActiveConvId(newConv.id);
    setMessages([]);
    setCurrentSessionId(newConv.id);
  }, [setMessages, setCurrentSessionId, activeConvId, messages]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend]
  );

  const handleTextareaInput = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
  }, []);

  return (
    <div className="flex h-[calc(100vh-7rem)] gap-4">
      {/* ── Sidebar ── */}
      {showSidebar && (
        <motion.aside
          initial={{ width: 0, opacity: 0 }}
          animate={{ width: 240, opacity: 1 }}
          exit={{ width: 0, opacity: 0 }}
          transition={{ duration: 0.2 }}
          className="flex-shrink-0 flex flex-col glass-card-static overflow-hidden"
        >
          <div className="p-3 border-b border-surface-200/60">
            <button onClick={handleNewConversation} className="btn-primary w-full text-xs py-2">
              <Plus size={14} />
              新对话
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {conversations.map((conv) => (
              <button
                key={conv.id}
                onClick={() => {
                  // Save current messages to current conversation before switching
                  setConversations((prev) =>
                    prev.map((c) =>
                      c.id === activeConvId ? { ...c, messages } : c
                    )
                  );
                  setActiveConvId(conv.id);
                  setMessages(conv.messages);
                  setCurrentSessionId(conv.id);
                }}
                className={`w-full text-left px-3 py-2 rounded-xl text-xs transition-all duration-150 truncate ${
                  conv.id === activeConvId
                    ? 'bg-brand-50 text-brand-700 font-medium'
                    : 'text-surface-600 hover:bg-surface-50'
                }`}
              >
                {conv.title}
              </button>
            ))}
          </div>

          <div className="p-3 border-t border-surface-200/60">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-surface-400 mb-2">
              AI 能力等级
            </p>
            <LevelIndicator level={currentLevel} />
          </div>
        </motion.aside>
      )}

      {/* ── Main Chat Area ── */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <div className="flex items-center gap-2 mb-3">
          <button
            onClick={() => setShowSidebar(!showSidebar)}
            className="p-1.5 rounded-lg text-surface-400 hover:text-surface-600 hover:bg-surface-100 transition-colors"
          >
            <BarChart3 size={16} />
          </button>
          <h2 className="text-sm font-semibold text-finance-800 font-display flex items-center gap-2">
            <Sparkles size={14} className="text-brand-500" />
            AI 工作空间
          </h2>
          {activeConv && (
            <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold border ${LEVEL_CONFIG[currentLevel].bg} ${LEVEL_CONFIG[currentLevel].color}`}>
              {LEVEL_CONFIG[currentLevel].label}
            </span>
          )}
        </div>

        {/* Messages */}
        <div className="flex-1 glass-card-static flex flex-col overflow-hidden">
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center h-full text-center">
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.4 }}
                >
                  <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-finance-500 to-finance-700 flex items-center justify-center shadow-glow">
                    <Bot size={28} className="text-white" />
                  </div>
                  <h3 className="text-lg font-semibold text-finance-800 font-display mb-1">
                    AI 财经工作空间
                  </h3>
                  <p className="text-sm text-surface-400 mb-6 max-w-sm">
                    我不是简单的问答工具，而是你的财经助手。我会理解你的意图、调用专业工具、分析数据，并给出可执行的建议。
                  </p>

                  <div className="mb-6 flex items-center gap-1.5 text-xs text-surface-500">
                    <Sparkles size={12} className="text-brand-500" />
                    <span>我的工作方式</span>
                  </div>

                  <div className="grid grid-cols-2 gap-2 max-w-md mb-6">
                    {[
                      { icon: <Target size={14} />, label: '理解意图', desc: '识别你的真实需求' },
                      { icon: <Wrench size={14} />, label: '调用工具', desc: '37个专业工具' },
                      { icon: <Brain size={14} />, label: '分析推理', desc: 'OAG本体推理链' },
                      { icon: <Lightbulb size={14} />, label: '执行建议', desc: '一键执行AI建议' },
                    ].map((item, i) => (
                      <motion.div
                        key={i}
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="flex items-start gap-2 p-3 rounded-xl bg-white border border-surface-100 text-left"
                      >
                        <div className="p-1.5 rounded-lg bg-brand-50 text-brand-600">
                          {item.icon}
                        </div>
                        <div>
                          <p className="text-xs font-semibold text-surface-700">{item.label}</p>
                          <p className="text-[10px] text-surface-400">{item.desc}</p>
                        </div>
                      </motion.div>
                    ))}
                  </div>

                  <div className="grid grid-cols-2 gap-2 max-w-md">
                    {SUGGESTED_PROMPTS.map((prompt) => (
                      <motion.button
                        key={prompt}
                        onClick={() => handleSend(prompt)}
                        className="text-left px-3 py-2.5 rounded-xl text-xs text-surface-600 bg-white border border-surface-200/60 hover:border-finance-300 hover:bg-finance-50 hover:text-finance-700 transition-all duration-150 shadow-sm"
                        whileHover={{ y: -1 }}
                        whileTap={{ scale: 0.98 }}
                      >
                        {prompt}
                      </motion.button>
                    ))}
                  </div>
                </motion.div>
              </div>
            )}

            <AnimatePresence>
              {messages.map((msg) => (
                <MessageBubble key={msg.id} message={msg} />
              ))}
            </AnimatePresence>

            <div ref={messagesEndRef} />
          </div>

          {/* Input Area */}
          <div className="p-4 border-t border-surface-200/60 bg-white/50 backdrop-blur-lg">
            {messages.length > 0 && messages.length < 2 && (
              <div className="flex flex-wrap gap-1.5 mb-3">
                {SUGGESTED_PROMPTS.map((prompt) => (
                  <button
                    key={prompt}
                    onClick={() => handleSend(prompt)}
                    className="px-2.5 py-1 rounded-lg text-[10px] font-medium text-brand-600 bg-brand-50 border border-brand-100 hover:bg-brand-100 transition-colors"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            )}

            <div className="flex items-end gap-2">
              <div className="flex-1 relative">
                <textarea
                  ref={inputRef}
                  value={input}
                  onChange={handleTextareaInput}
                  onKeyDown={handleKeyDown}
                  placeholder="用自然语言告诉我你要做什么..."
                  rows={1}
                  className="w-full px-4 py-2.5 rounded-xl bg-surface-50 border border-surface-200/60 text-sm text-surface-800 placeholder:text-surface-400 focus:outline-none focus:border-finance-400 focus:ring-2 focus:ring-finance-100 resize-none transition-all duration-150"
                  disabled={isStreaming}
                />
              </div>

              {isStreaming ? (
                <motion.button
                  onClick={handleAbort}
                  className="flex-shrink-0 w-10 h-10 rounded-xl bg-alert-500 text-white flex items-center justify-center shadow-sm hover:bg-alert-600 transition-colors"
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                >
                  <Square size={16} />
                </motion.button>
              ) : (
                <motion.button
                  onClick={() => handleSend()}
                  disabled={!input.trim()}
                  className="flex-shrink-0 w-10 h-10 rounded-xl bg-gradient-to-br from-brand-500 to-finance-600 text-white flex items-center justify-center shadow-sm disabled:opacity-40 disabled:cursor-not-allowed transition-all duration-150"
                  whileHover={input.trim() ? { scale: 1.05 } : {}}
                  whileTap={input.trim() ? { scale: 0.95 } : {}}
                >
                  <Send size={16} />
                </motion.button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
