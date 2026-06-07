"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { loadBrokerModel, saveBrokerModel } from "./networkPrefs";
import type { PendingTask } from "./taskThread";

interface NetworkContextValue {
  pendingTasks: PendingTask[];
  taskBudgets: Record<string, number>;
  addPendingTask: (task: PendingTask) => void;
  removePendingTask: (taskId: string) => void;
  brokerModel: string;
  setBrokerModel: (modelId: string) => void;
  agentsOpen: boolean;
  setAgentsOpen: (open: boolean) => void;
  scrollNonce: number;
  bumpScroll: () => void;
}

const NetworkContext = createContext<NetworkContextValue | null>(null);

export function NetworkProvider({ children }: { children: ReactNode }) {
  const [pendingTasks, setPendingTasks] = useState<PendingTask[]>([]);
  const [taskBudgets, setTaskBudgets] = useState<Record<string, number>>({});
  const [brokerModel, setBrokerModelState] = useState(loadBrokerModel);
  const [agentsOpen, setAgentsOpen] = useState(false);
  const [scrollNonce, setScrollNonce] = useState(0);

  useEffect(() => {
    setBrokerModelState(loadBrokerModel());
  }, []);

  const addPendingTask = useCallback((task: PendingTask) => {
    setPendingTasks((prev) => [...prev.filter((p) => p.task_id !== task.task_id), task]);
    setTaskBudgets((prev) => ({ ...prev, [task.task_id]: task.budget }));
    setScrollNonce((n) => n + 1);
  }, []);

  const removePendingTask = useCallback((taskId: string) => {
    setPendingTasks((prev) => prev.filter((p) => p.task_id !== taskId));
  }, []);

  const setBrokerModel = useCallback((modelId: string) => {
    saveBrokerModel(modelId);
    setBrokerModelState(modelId);
  }, []);

  const bumpScroll = useCallback(() => {
    setScrollNonce((n) => n + 1);
  }, []);

  const value = useMemo(
    () => ({
      pendingTasks,
      taskBudgets,
      addPendingTask,
      removePendingTask,
      brokerModel,
      setBrokerModel,
      agentsOpen,
      setAgentsOpen,
      scrollNonce,
      bumpScroll,
    }),
    [
      pendingTasks,
      taskBudgets,
      addPendingTask,
      removePendingTask,
      brokerModel,
      setBrokerModel,
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
