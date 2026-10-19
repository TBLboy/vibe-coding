export interface MemoryChangeSignals {
  unfinishedResumableWork?: boolean;
  blockerNeedsFollowUp?: boolean;
  importantFeatureCompleted?: boolean;
  projectStageChanged?: boolean;
  materialBusinessDecision?: boolean;
  materialTechnicalDecision?: boolean;
  importantLimitationFound?: boolean;
  importantBlockerResolved?: boolean;
}

export function shouldWriteCurrentSession(signals: MemoryChangeSignals): boolean {
  return signals.unfinishedResumableWork === true || signals.blockerNeedsFollowUp === true;
}

export function shouldUpdateProgress(signals: MemoryChangeSignals): boolean {
  return (
    signals.importantFeatureCompleted === true ||
    signals.projectStageChanged === true ||
    signals.materialBusinessDecision === true ||
    signals.materialTechnicalDecision === true ||
    signals.importantLimitationFound === true ||
    signals.importantBlockerResolved === true
  );
}
