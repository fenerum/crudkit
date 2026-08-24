import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { toast } from "react-toastify";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../context/AuthContext";
import CrudKitAPIClient from "@/data/api";
import { formatDuration } from "../utils/time";

const TimeTracker = () => {
  const client = new CrudKitAPIClient();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const { pathname } = useLocation();
  const [isAdjustModalOpen, setIsAdjustModalOpen] = useState(false);
  const [notes, setNotes] = useState("");
  const [isDetailPage, setIsDetailPage] = useState(false);
  const [currentObjectInfo, setCurrentObjectInfo] = useState(null);
  const [elapsedTime, setElapsedTime] = useState(0);
  const [timer, setTimer] = useState(null);
  const [adjustedHours, setAdjustedHours] = useState(0);
  const [adjustedMinutes, setAdjustedMinutes] = useState(0);
  const [adjustedSeconds, setAdjustedSeconds] = useState(0);

  useEffect(() => {
    const pathParts = pathname.split("/").filter(part => part !== "");

    if (pathParts.length === 1 && /^[A-Z]{3}\d+$/.test(pathParts[0])) {
      const id = pathParts[0];
      const modelType = id.substring(0, 3);
      setIsDetailPage(true);
      setCurrentObjectInfo({ modelType, objectId: id });
    } else {
      setIsDetailPage(false);
      setCurrentObjectInfo(null);
    }
  }, [pathname]);

  const { data: activeWorkLog, isLoading } = useQuery({
    queryKey: ['activeWorkLog', user?.id],
    queryFn: async () => {
      try {
        const result = await client.list("WLG", {
          "created_by": user?.id,
          "end_at__isnull": "True",
          "deleted": "False",
          "ordering": "-created_at"
        });

        const workLogs = result?.isPaginated ? result.results : result;

        if (workLogs && Array.isArray(workLogs) && workLogs.length > 0) {
          const activeWorkLogs = workLogs.filter(item => item.end_at === null);
          if (activeWorkLogs.length > 0) {
            return [activeWorkLogs[0]];
          }
          return activeWorkLogs;
        }

        return [];
      } catch (error) {
        console.error("Error fetching active work logs:", error);
        throw error;
      }
    },
    enabled: !!user?.id,
    refetchInterval: 30000,
  });

  useEffect(() => {
    if (Array.isArray(activeWorkLog) && activeWorkLog.length > 0 && activeWorkLog[0].notes) {
      setNotes(activeWorkLog[0].notes);
    }
  }, [activeWorkLog]);

  const initializeAdjustedTime = () => {
    const hours = Math.floor(elapsedTime / 3600);
    const minutes = Math.floor((elapsedTime % 3600) / 60);
    const seconds = elapsedTime % 60;
    setAdjustedHours(hours);
    setAdjustedMinutes(minutes);
    setAdjustedSeconds(seconds);
  };

  useEffect(() => {
    if (Array.isArray(activeWorkLog) && activeWorkLog.length > 0 && activeWorkLog[0].end_at === null) {
      const startTime = new Date(activeWorkLog[0].created_at);

      const intervalId = setInterval(() => {
        const now = new Date();
        const diff = Math.floor((now - startTime) / 1000);
        setElapsedTime(diff);
      }, 1000);

      setTimer(intervalId);

      return () => clearInterval(intervalId);
    } else {
      clearInterval(timer);
      setTimer(null);
      setElapsedTime(0);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeWorkLog]);

  const startTracking = useMutation({
    mutationFn: () => {
      if (!currentObjectInfo) return;
      return client.create("WLG", {
        related_object: currentObjectInfo.objectId,
        notes: "",
        end_at: null,
      });
    },
    onSuccess: (data) => {
      if (data) {
        queryClient.setQueryData(['activeWorkLog', user?.id], [data]);
      }
      queryClient.refetchQueries({ queryKey: ['activeWorkLog'] });
      toast.success("Time tracking started");
    },
    onError: (error) => {
      console.error("Failed to start time tracking:", error);
      toast.error("Failed to start time tracking");
    },
  });

  const stopTracking = useMutation({
    mutationFn: () => {
      if (!Array.isArray(activeWorkLog) || activeWorkLog.length === 0) return;
      const workLogId = activeWorkLog[0].id;
      return client.partialUpdate("WLG", workLogId, {
        end_at: new Date().toISOString(),
        notes,
      });
    },
    onSuccess: () => {
      queryClient.setQueryData(['activeWorkLog', user?.id], []);
      queryClient.refetchQueries({ queryKey: ['activeWorkLog'] });
      setNotes("");
      toast.success("Time tracking stopped");
    },
    onError: (error) => {
      console.error("Failed to stop time tracking:", error);
      toast.error("Failed to stop time tracking");
    },
  });

  const adjustTracking = useMutation({
    mutationFn: () => {
      if (!Array.isArray(activeWorkLog) || activeWorkLog.length === 0) return;

      const workLogId = activeWorkLog[0].id;
      const createdAt = new Date(activeWorkLog[0].created_at);

      const totalSeconds = (adjustedHours * 3600) + (adjustedMinutes * 60) + adjustedSeconds;
      const originalDuration = elapsedTime;
      const updateData = { notes };

      if (totalSeconds !== originalDuration) {
        const endAt = new Date(createdAt.getTime() + (totalSeconds * 1000));
        updateData.end_at = endAt.toISOString();
      }

      return client.partialUpdate("WLG", workLogId, updateData);
    },
    onSuccess: (data) => {
      if (data && data.end_at) {
        queryClient.setQueryData(['activeWorkLog', user?.id], []);
      } else if (data) {
        queryClient.setQueryData(['activeWorkLog', user?.id], [data]);
      }
      queryClient.refetchQueries({ queryKey: ['activeWorkLog'] });
      setIsAdjustModalOpen(false);
      toast.success("Time tracking updated");
    },
    onError: (error) => {
      console.error("Failed to update time tracking:", error);
      toast.error("Failed to update time tracking");
    },
  });

  if (isLoading) {
    return <span className="text-fg-3 text-xs px-1.5">…</span>;
  }

  const hasActiveWorkLog = Array.isArray(activeWorkLog) && activeWorkLog.length > 0;
  const activeObjectId = hasActiveWorkLog ? activeWorkLog[0].related_object : "";

  return (
    <>
      {hasActiveWorkLog ? (
        <span className="inline-flex items-center gap-1.5 h-[26px] px-2 rounded-md bg-bg-2 border border-border-1 text-xs">
          <span className="ck-mono text-fg-1 font-medium">{formatDuration(elapsedTime)}</span>
          <Link to={`/${activeObjectId}`} className="text-primary-300 hover:text-primary-200 ck-mono">
            {activeObjectId}
          </Link>
          <button
            type="button"
            className="ck-icon-btn ck-icon-btn-sm"
            onClick={() => { initializeAdjustedTime(); setIsAdjustModalOpen(true); }}
            aria-label="Adjust tracked time"
            title="Adjust tracked time"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 20h9" />
              <path d="M16.5 3.5a2.121 2.121 0 1 1 3 3L7 19l-4 1 1-4 12.5-12.5z" />
            </svg>
          </button>
          <button
            type="button"
            className="ck-icon-btn ck-icon-btn-sm"
            onClick={() => stopTracking.mutate()}
            aria-label="Stop time tracking"
            title="Stop"
            style={{ color: 'var(--danger)' }}
          >
            <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor">
              <rect x="6" y="6" width="12" height="12" rx="1" />
            </svg>
          </button>
        </span>
      ) : (
        <button
          type="button"
          className="ck-btn ck-btn-secondary ck-btn-sm"
          disabled={!isDetailPage}
          onClick={() => startTracking.mutate()}
          title={isDetailPage ? "Start time tracking" : "Open a record to track time"}
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <polyline points="12 6 12 12 16 14" />
          </svg>
          <span>Start</span>
        </button>
      )}

      {isAdjustModalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center"
          style={{ background: 'rgba(0,0,0,0.6)' }}
          onClick={() => setIsAdjustModalOpen(false)}
        >
          <div
            className="rounded-lg border border-border-1 bg-bg-2 p-5 w-full max-w-md"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="text-lg font-semibold text-fg-1 mb-4">Complete with Custom Time</h2>

            <div className="eyebrow mb-2">Duration</div>
            <div className="flex gap-2 mb-3">
              {[
                { label: 'hours', value: adjustedHours, set: setAdjustedHours, max: null },
                { label: 'min', value: adjustedMinutes, set: setAdjustedMinutes, max: 59 },
                { label: 'sec', value: adjustedSeconds, set: setAdjustedSeconds, max: 59 },
              ].map(({ label, value, set, max }) => (
                <div key={label} className="flex-1 flex flex-col items-center">
                  <input
                    type="number"
                    inputMode="numeric"
                    value={String(value)}
                    onChange={(e) => {
                      const v = parseInt(e.target.value) || 0;
                      set(max != null ? Math.min(v, max) : v);
                    }}
                    className="ck-input font-mono text-center w-full"
                    placeholder="0"
                  />
                  <span className="text-xs text-fg-3 mt-1">{label}</span>
                </div>
              ))}
            </div>

            <div className="eyebrow mb-2">Notes</div>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="ck-input w-full"
              rows={4}
              placeholder="Add notes about this work session"
            />

            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                className="ck-btn ck-btn-ghost ck-btn-sm"
                onClick={() => setIsAdjustModalOpen(false)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="ck-btn ck-btn-primary ck-btn-sm"
                onClick={() => adjustTracking.mutate()}
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default TimeTracker;
