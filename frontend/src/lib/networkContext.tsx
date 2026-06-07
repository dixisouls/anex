"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { api, ApiError } from "./api";
import {
  DEFAULT_PREFERRED_TIER,
  loadBrokerModel,
  loadHiddenTaskIds,
  loadPreferredTier,
  loadSelectedTaskId,
  saveBrokerModel,
  saveHiddenTaskIds,
  savePreferredTier,
  saveSelectedTaskId,
} from "./networkPrefs";
import { taskDetailToState, type PendingTask } from "./taskThread";
import { useUser } from "./user";
import type { TaskState } from "./pipeline";
import type { Tier } from "./types";

export interface TasksError {
  message: string;
  status?: number;
}

interface NetworkContextValue {
  pendingTasks: PendingTask[];
  taskBudgets: Record<string, number>;
  dbTasks: Record<string, TaskState>;
  hiddenTaskIds: Set<string>;
  selectedTaskId: string | null;
  isNewChat: boolean;
  tasksLoading: boolean;
  tasksError: TasksError | null;
  addPendingTask: (task: PendingTask) => void;
  removePendingTask: (taskId: string) => void;
  setSelectedTaskId: (taskId: string | null) => void;
  startNewChat: () => void;
  hideTask: (taskId: string) => Promise<void>;
  hydrateTasks: () => Promise<void>;
  brokerModel: string;
  setBrokerModel: (modelId: string) => void;
  preferredTier: Tier;
  setPreferredTier: (tier: Tier) => void;
  agentsOpen: boolean;
  setAgentsOpen: (open: boolean) => void;
  scrollNonce: number;
  bumpScroll: () => void;
}

const NetworkContext = createContext<NetworkContextValue | null>(null);

export function NetworkProvider({ children }: { children: ReactNode }) {
  const { userId } = useUser();
  const [pendingTasks, setPendingTasks] = useState<PendingTask[]>([]);
  const [taskBudgets, setTaskBudgets] = useState<Record<string, number>>({});
  const [dbTasks, setDbTasks] = useState<Record<string, TaskState>>({});
  const [hiddenTaskIds, setHiddenTaskIds] = useState<Set<string>>(new Set());
  const [selectedTaskId, setSelectedTaskIdState] = useState<string | null>(null);
  const [isNewChat, setIsNewChat] = useState(false);
  const [tasksLoading, setTasksLoading] = useState(false);
  const [tasksError, setTasksError] = useState<TasksError | null>(null);
  const [brokerModel, setBrokerModelState] = useState(loadBrokerModel);
  const [preferredTier, setPreferredTierState] = useState<Tier>(
    DEFAULT_PREFERRED_TIER,
  );
  const [agentsOpen, setAgentsOpen] = useState(false);
  const [scrollNonce, setScrollNonce] = useState(0);
  const hydrateRef = useRef(0);

  useEffect(() => {
    setBrokerModelState(loadBrokerModel());
    setPreferredTierState(loadPreferredTier());
    setSelectedTaskIdState(loadSelectedTaskId());
    if (userId) setHiddenTaskIds(loadHiddenTaskIds(userId));
  }, [userId]);

  const hydrateTasks = useCallback(async () => {
    if (!userId) {
      setTasksError(null);
      return;
    }
    const seq = ++hydrateRef.current;
    setTasksLoading(true);
    try {
      const res = await api.getUserTasks(userId);
      if (seq !== hydrateRef.current) return;
      const hidden = loadHiddenTaskIds(userId);
      const next: Record<string, TaskState> = {};
      for (const t of res.tasks) {
        if (!hidden.has(t.task_id)) next[t.task_id] = taskDetailToState(t);
      }
      setDbTasks(next);
      setTasksError(null);
    } catch (e) {
      if (seq !== hydrateRef.current) return;
      if (e instanceof ApiError) {
        setTasksError({ message: String(e.message), status: e.status });
      } else {
        setTasksError({
          message: e instanceof Error ? e.message : "Failed to load task history",
        });
      }
    } finally {
      if (seq === hydrateRef.current) setTasksLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    void hydrateTasks();
  }, [hydrateTasks]);

  useEffect(() => {
    if (!userId) return;
    const hasRunning = Object.values(dbTasks).some((t) => {
      const subs = Object.values(t.subtasks);
      if (subs.length === 0) return true;
      return subs.some((s) => !s.skipped && s.stage !== "scored");
    });
    if (!hasRunning && pendingTasks.length === 0) return;
    const id = window.setInterval(() => void hydrateTasks(), 30_000);
    return () => window.clearInterval(id);
  }, [userId, dbTasks, pendingTasks.length, hydrateTasks]);

  const setSelectedTaskId = useCallback((taskId: string | null) => {
    saveSelectedTaskId(taskId);
    setSelectedTaskIdState(taskId);
    if (taskId) setIsNewChat(false);
  }, []);

  const startNewChat = useCallback(() => {
    saveSelectedTaskId(null);
    setSelectedTaskIdState(null);
    setIsNewChat(true);
  }, []);

  const hideTask = useCallback(
    async (taskId: string) => {
      if (userId) {
        const nextHidden = new Set(loadHiddenTaskIds(userId));
        nextHidden.add(taskId);
        saveHiddenTaskIds(userId, nextHidden);
        setHiddenTaskIds(nextHidden);
        try {
          await api.hideUserTask(userId, taskId);
        } catch {
          /* still hidden locally */
        }
      }
      setPendingTasks((prev) => prev.filter((p) => p.task_id !== taskId));
      setTaskBudgets((prev) => {
        const next = { ...prev };
        delete next[taskId];
        return next;
      });
      setDbTasks((prev) => {
        const next = { ...prev };
        delete next[taskId];
        return next;
      });
      if (selectedTaskId === taskId) {
        saveSelectedTaskId(null);
        setSelectedTaskIdState(null);
        setIsNewChat(true);
      }
    },
    [userId, selectedTaskId],
  );

  const addPendingTask = useCallback((task: PendingTask) => {
    setIsNewChat(false);
    setPendingTasks((prev) => [
      ...prev.filter((p) => p.task_id !== task.task_id),
      task,
    ]);
    setTaskBudgets((prev) => ({ ...prev, [task.task_id]: task.budget }));
    saveSelectedTaskId(task.task_id);
    setSelectedTaskIdState(task.task_id);
    setScrollNonce((n) => n + 1);
  }, []);

  const removePendingTask = useCallback((taskId: string) => {
    setPendingTasks((prev) => prev.filter((p) => p.task_id !== taskId));
  }, []);

  const setBrokerModel = useCallback((modelId: string) => {
    saveBrokerModel(modelId);
    setBrokerModelState(modelId);
  }, []);

  const setPreferredTier = useCallback((tier: Tier) => {
    savePreferredTier(tier);
    setPreferredTierState(tier);
  }, []);

  const bumpScroll = useCallback(() => {
    setScrollNonce((n) => n + 1);
  }, []);

  const value = useMemo(
    () => ({
      pendingTasks,
      taskBudgets,
      dbTasks,
      hiddenTaskIds,
      selectedTaskId,
      isNewChat,
      tasksLoading,
      tasksError,
      addPendingTask,
      removePendingTask,
      setSelectedTaskId,
      startNewChat,
      hideTask,
      hydrateTasks,
      brokerModel,
      setBrokerModel,
      preferredTier,
      setPreferredTier,
      agentsOpen,
      setAgentsOpen,
      scrollNonce,
      bumpScroll,
    }),
    [
      pendingTasks,
      taskBudgets,
      dbTasks,
      hiddenTaskIds,
      selectedTaskId,
      isNewChat,
      tasksLoading,
      tasksError,
      addPendingTask,
      removePendingTask,
      setSelectedTaskId,
      startNewChat,
      hideTask,
      hydrateTasks,
      brokerModel,
      setBrokerModel,
      preferredTier,
      setPreferredTier,
      agentsOpen,
      scrollNonce,
      bumpScroll,
    ],
  );

  return (
    <NetworkContext.Provider value={value}>{children}</NetworkContext.Provider>
  );
}

export function useNetwork() {
  const ctx = useContext(NetworkContext);
  if (!ctx) throw new Error("useNetwork must be used within NetworkProvider");
  return ctx;
}
