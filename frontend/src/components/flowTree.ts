/**
 * Question-only tree ↔ flat flow[] compile.
 * Answer buttons live inside each question (not as tree rows).
 * Nested child questions are submenu items; triggerOptionId links to a parent button.
 */

import type { FlowStep, FlowStepOption } from "../api";

export type InteractiveOpts = {
  business_types?: Array<{
    id: string;
    title: string;
    description?: string;
    value?: string;
    next_key?: string;
  }>;
  locations?: Array<{ id: string; title: string; value?: string; next_key?: string }>;
  current_system?: Array<{
    id: string;
    title: string;
    sheet_value?: string;
    next_key?: string;
  }>;
};

const ANCHOR_KEYS = new Set(["GREETING", "BUSINESS_NAME", "CONFIRMED", "STALLED"]);
const BUILTIN_KEYS = new Set([
  "BUSINESS_TYPE",
  "LOCATIONS",
  "CURRENT_SYSTEM",
  "SCHEDULING",
]);

export type FlatOption = {
  id: string;
  title: string;
  description?: string;
  value?: string;
  sheet_value?: string;
};

export type TreeQuestionNode = {
  kind: "question";
  step: FlowStep;
  /** Answer buttons — edited inside the question panel */
  options: FlatOption[];
  /**
   * Follow-up questions shown as indented sub-items.
   * triggerOptionId = parent button that jumps here (niche branch).
   * null = after this text question (step.next_key) or not linked yet.
   */
  children: TreeChildLink[];
};

export type TreeChildLink = {
  triggerOptionId: string | null;
  question: TreeQuestionNode;
};

function normKey(k: string | undefined | null): string {
  return (k || "").trim().toUpperCase().replace(/\s+/g, "_");
}

function isTextLike(step: FlowStep): boolean {
  const t = step.type || "";
  return t === "text_question" || t === "free_text_capture";
}

export function arrangableFromFlow(flow: FlowStep[]): FlowStep[] {
  return flow.filter((s) => !ANCHOR_KEYS.has(normKey(s.key)));
}

export function resolveOptions(
  step: FlowStep,
  interactive: InteractiveOpts
): FlatOption[] {
  const key = normKey(step.key);
  const ok = step.options_key;
  if (ok === "business_types" || key === "BUSINESS_TYPE") {
    return (interactive.business_types || []).map((r) => ({
      id: r.id,
      title: r.title || "",
      description: r.description || "",
      value: r.value || r.title || "",
    }));
  }
  if (ok === "locations" || key === "LOCATIONS") {
    return (interactive.locations || []).map((r) => ({
      id: r.id,
      title: r.title || "",
      value: r.value || r.title || "",
    }));
  }
  if (ok === "current_system" || key === "CURRENT_SYSTEM") {
    return (interactive.current_system || []).map((r) => ({
      id: r.id,
      title: r.title || "",
      sheet_value: r.sheet_value || r.title || "",
      value: r.sheet_value || r.title || "",
    }));
  }
  if (key === "SCHEDULING") return [];
  return (step.options || []).map((o) => ({
    id: o.id,
    title: o.title || "",
    description: o.description || "",
    value: o.value || o.sheet_value || o.title || "",
    sheet_value: o.sheet_value,
  }));
}

function optionNextKeyMap(
  step: FlowStep,
  interactive: InteractiveOpts
): Map<string, string> {
  /** optionId → next_key */
  const map = new Map<string, string>();
  const key = normKey(step.key);
  const ok = step.options_key;
  if (ok === "business_types" || key === "BUSINESS_TYPE") {
    for (const r of interactive.business_types || []) {
      if (r.next_key) map.set(r.id, normKey(r.next_key));
    }
    return map;
  }
  if (ok === "locations" || key === "LOCATIONS") {
    for (const r of interactive.locations || []) {
      if (r.next_key) map.set(r.id, normKey(r.next_key));
    }
    return map;
  }
  if (ok === "current_system" || key === "CURRENT_SYSTEM") {
    for (const r of interactive.current_system || []) {
      if (r.next_key) map.set(r.id, normKey(r.next_key));
    }
    return map;
  }
  for (const o of step.options || []) {
    if (o.next_key) map.set(o.id, normKey(o.next_key));
  }
  return map;
}

function collectOptionInbound(
  steps: FlowStep[],
  interactive: InteractiveOpts
): Set<string> {
  const inbound = new Set<string>();
  for (const step of steps) {
    for (const nk of optionNextKeyMap(step, interactive).values()) {
      if (nk) inbound.add(nk);
    }
  }
  return inbound;
}

function collectTextNested(
  steps: FlowStep[],
  optionInbound: Set<string>
): Set<string> {
  const nested = new Set<string>();
  for (const step of steps) {
    if (!isTextLike(step)) continue;
    const nk = normKey(step.next_key);
    if (!nk || BUILTIN_KEYS.has(nk) || optionInbound.has(nk)) continue;
    nested.add(nk);
  }
  return nested;
}

function buildQuestion(
  step: FlowStep,
  byKey: Map<string, FlowStep>,
  interactive: InteractiveOpts,
  optionInbound: Set<string>,
  textNested: Set<string>,
  visiting: Set<string>
): TreeQuestionNode {
  const key = normKey(step.key);
  if (visiting.has(key)) {
    return { kind: "question", step, options: resolveOptions(step, interactive), children: [] };
  }
  visiting.add(key);

  const options = resolveOptions(step, interactive);
  const nextByOpt = optionNextKeyMap(step, interactive);
  const children: TreeChildLink[] = [];
  const usedDest = new Set<string>();

  for (const [optId, destKey] of nextByOpt) {
    if (!destKey || usedDest.has(destKey)) continue;
    if (!optionInbound.has(destKey) && !textNested.has(destKey)) continue;
    const dest = byKey.get(destKey);
    if (!dest) continue;
    usedDest.add(destKey);
    children.push({
      triggerOptionId: optId,
      question: buildQuestion(dest, byKey, interactive, optionInbound, textNested, visiting),
    });
  }

  if (options.length === 0 && isTextLike(step)) {
    const nk = normKey(step.next_key);
    if (nk && textNested.has(nk) && !usedDest.has(nk)) {
      const dest = byKey.get(nk);
      if (dest) {
        usedDest.add(nk);
        children.push({
          triggerOptionId: null,
          question: buildQuestion(dest, byKey, interactive, optionInbound, textNested, visiting),
        });
      }
    }
  }

  visiting.delete(key);
  return { kind: "question", step, options, children };
}

export function flowToTree(
  flow: FlowStep[],
  interactive: InteractiveOpts = {}
): TreeQuestionNode[] {
  const steps = arrangableFromFlow(flow);
  const byKey = new Map(steps.map((s) => [normKey(s.key), s]));
  const optionInbound = collectOptionInbound(steps, interactive);
  const textNested = collectTextNested(steps, optionInbound);
  const nestedAway = new Set([...optionInbound, ...textNested]);
  const roots = steps.filter((s) => !nestedAway.has(normKey(s.key)));
  const visiting = new Set<string>();
  return roots.map((s) =>
    buildQuestion(s, byKey, interactive, optionInbound, textNested, visiting)
  );
}

export type FlatTreeRow = {
  kind: "question";
  id: string;
  depth: number;
  node: TreeQuestionNode;
  /** Parent question step id when nested */
  parentStepId?: string;
};

export function flattenTree(roots: TreeQuestionNode[]): FlatTreeRow[] {
  const rows: FlatTreeRow[] = [];
  function walk(node: TreeQuestionNode, depth: number, parentStepId?: string) {
    rows.push({
      kind: "question",
      id: `q:${node.step.id}`,
      depth,
      node,
      parentStepId,
    });
    for (const child of node.children) {
      walk(child.question, depth + 1, node.step.id);
    }
  }
  for (const r of roots) walk(r, 0);
  return rows;
}

function cloneQuestion(node: TreeQuestionNode): TreeQuestionNode {
  return {
    kind: "question",
    step: {
      ...node.step,
      options: (node.step.options || []).map((o) => ({ ...o })),
    },
    options: node.options.map((o) => ({ ...o })),
    children: node.children.map((c) => ({
      triggerOptionId: c.triggerOptionId,
      question: cloneQuestion(c.question),
    })),
  };
}

export function cloneTree(roots: TreeQuestionNode[]): TreeQuestionNode[] {
  return roots.map(cloneQuestion);
}

export function extractQuestion(
  roots: TreeQuestionNode[],
  stepId: string
): { tree: TreeQuestionNode[]; removed: TreeQuestionNode | null } {
  const tree = cloneTree(roots);
  let removed: TreeQuestionNode | null = null;

  function strip(node: TreeQuestionNode): void {
    const nextChildren: TreeChildLink[] = [];
    for (const c of node.children) {
      if (c.question.step.id === stepId) {
        removed = c.question;
        continue;
      }
      strip(c.question);
      nextChildren.push(c);
    }
    node.children = nextChildren;
  }

  const nextRoots: TreeQuestionNode[] = [];
  for (const r of tree) {
    if (r.step.id === stepId) {
      removed = r;
      continue;
    }
    strip(r);
    nextRoots.push(r);
  }
  return { tree: nextRoots, removed };
}

function findQuestion(
  roots: TreeQuestionNode[],
  stepId: string
): TreeQuestionNode | null {
  function walk(node: TreeQuestionNode): TreeQuestionNode | null {
    if (node.step.id === stepId) return node;
    for (const c of node.children) {
      const hit = walk(c.question);
      if (hit) return hit;
    }
    return null;
  }
  for (const r of roots) {
    const hit = walk(r);
    if (hit) return hit;
  }
  return null;
}

/** Nest active under over as a child; optionally assign triggerOptionId. */
export function nestQuestionUnder(
  roots: TreeQuestionNode[],
  activeStepId: string,
  parentStepId: string,
  triggerOptionId: string | null = null
): TreeQuestionNode[] {
  const { tree, removed } = extractQuestion(roots, activeStepId);
  if (!removed) return roots;
  const parent = findQuestion(tree, parentStepId);
  if (!parent) return [...tree, removed];

  // Default trigger: first parent option that has no child yet
  let trigger = triggerOptionId;
  if (trigger == null && parent.options.length > 0) {
    const used = new Set(
      parent.children.map((c) => c.triggerOptionId).filter(Boolean) as string[]
    );
    const free = parent.options.find((o) => !used.has(o.id));
    trigger = free?.id ?? parent.options[0]?.id ?? null;
  }

  parent.children = [
    ...parent.children,
    { triggerOptionId: trigger, question: cloneQuestion(removed) },
  ];
  return tree;
}

export function reorderRoots(
  roots: TreeQuestionNode[],
  activeStepId: string,
  overStepId: string
): TreeQuestionNode[] {
  const from = roots.findIndex((r) => r.step.id === activeStepId);
  const to = roots.findIndex((r) => r.step.id === overStepId);
  if (from < 0 || to < 0 || from === to) return roots;
  const next = [...roots];
  const [item] = next.splice(from, 1);
  next.splice(to, 0, item);
  return next;
}

export function setChildTrigger(
  roots: TreeQuestionNode[],
  childStepId: string,
  triggerOptionId: string | null
): TreeQuestionNode[] {
  const tree = cloneTree(roots);
  function walk(node: TreeQuestionNode): boolean {
    for (const c of node.children) {
      if (c.question.step.id === childStepId) {
        c.triggerOptionId = triggerOptionId;
        return true;
      }
      if (walk(c.question)) return true;
    }
    return false;
  }
  for (const r of tree) walk(r);
  return tree;
}

function collectQuestionsInOrder(roots: TreeQuestionNode[]): TreeQuestionNode[] {
  const out: TreeQuestionNode[] = [];
  function walk(node: TreeQuestionNode) {
    out.push(node);
    for (const c of node.children) walk(c.question);
  }
  for (const r of roots) walk(r);
  return out;
}

export function treeToFlow(
  roots: TreeQuestionNode[],
  fullFlow: FlowStep[],
  interactive: InteractiveOpts
): { flow: FlowStep[]; interactive: InteractiveOpts } {
  const anchorsBefore = fullFlow.filter((s) => {
    const k = normKey(s.key);
    return k === "GREETING" || k === "BUSINESS_NAME";
  });
  const anchorsAfter = fullFlow.filter((s) => {
    const k = normKey(s.key);
    return k === "CONFIRMED" || k === "STALLED";
  });

  const ordered = collectQuestionsInOrder(roots);
  const rootIds = new Set(roots.map((r) => r.step.id));

  function mergeTargetFor(node: TreeQuestionNode): string | null {
    for (let i = 0; i < roots.length; i++) {
      const owned = collectQuestionsInOrder([roots[i]]);
      if (owned.some((q) => q.step.id === node.step.id)) {
        if (roots[i].step.id === node.step.id) return null;
        const nextRoot = roots[i + 1];
        if (nextRoot) return normKey(nextRoot.step.key);
        return "CONFIRMED";
      }
    }
    return "CONFIRMED";
  }

  const interactiveOut: InteractiveOpts = {
    ...interactive,
    business_types: (interactive.business_types || []).map((r) => {
      const { next_key: _, ...rest } = r as typeof r & { next_key?: string };
      return { ...rest };
    }),
    locations: (interactive.locations || []).map((r) => {
      const { next_key: _, ...rest } = r as typeof r & { next_key?: string };
      return { ...rest };
    }),
    current_system: (interactive.current_system || []).map((r) => {
      const { next_key: _, ...rest } = r as typeof r & { next_key?: string };
      return { ...rest };
    }),
  };

  const arrangable: FlowStep[] = [];

  for (const q of ordered) {
    const key = normKey(q.step.key);
    const isRoot = rootIds.has(q.step.id);

    // Map trigger → child key
    const optNext = new Map<string, string>();
    let textThen: string | null = null;
    for (const c of q.children) {
      const dest = normKey(c.question.step.key);
      if (c.triggerOptionId) {
        optNext.set(c.triggerOptionId, dest);
      } else if (!textThen) {
        textThen = dest;
      }
    }

    let next_key: string | null = textThen;
    if (!isRoot && !textThen && q.children.length === 0) {
      next_key = mergeTargetFor(q);
    } else if (!isRoot && q.children.length > 0 && !textThen) {
      next_key = mergeTargetFor(q);
    } else if (!isRoot && !q.children.length) {
      next_key = mergeTargetFor(q);
    }

    const optionsWithNext: FlowStepOption[] = q.options.map((o) => ({
      id: o.id,
      title: o.title,
      description: o.description,
      value: o.value,
      sheet_value: o.sheet_value,
      ...(optNext.get(o.id) ? { next_key: optNext.get(o.id) } : {}),
    }));

    const ok = q.step.options_key;
    if (ok === "business_types" || key === "BUSINESS_TYPE") {
      interactiveOut.business_types = q.options.map((o) => ({
        id: o.id,
        title: o.title,
        value: o.value || o.title,
        description: o.description || "",
        ...(optNext.get(o.id) ? { next_key: optNext.get(o.id) } : {}),
      }));
    } else if (ok === "locations" || key === "LOCATIONS") {
      interactiveOut.locations = q.options.map((o) => ({
        id: o.id,
        title: o.title,
        value: o.value || o.title,
        ...(optNext.get(o.id) ? { next_key: optNext.get(o.id) } : {}),
      }));
    } else if (ok === "current_system" || key === "CURRENT_SYSTEM") {
      interactiveOut.current_system = q.options.map((o) => ({
        id: o.id,
        title: o.title,
        sheet_value: o.sheet_value || o.value || o.title,
        ...(optNext.get(o.id) ? { next_key: optNext.get(o.id) } : {}),
      }));
    }

    arrangable.push({
      ...q.step,
      next_key,
      options:
        key === "SCHEDULING" || ok
          ? []
          : optionsWithNext.map((o) => {
              const { next_key: nk, ...rest } = o;
              return nk ? { ...rest, next_key: nk } : rest;
            }),
    });
  }

  const seen = new Set(arrangable.map((s) => normKey(s.key)));
  for (const s of arrangableFromFlow(fullFlow)) {
    if (!seen.has(normKey(s.key))) {
      arrangable.push({ ...s, next_key: s.next_key || null });
    }
  }

  return {
    flow: [...anchorsBefore, ...arrangable, ...anchorsAfter],
    interactive: interactiveOut,
  };
}

export function questionTitle(step: FlowStep): string {
  const key = normKey(step.key);
  if ((step.label || "").trim()) return (step.label || "").trim();
  if (key === "BUSINESS_TYPE") return "Business type";
  if (key === "LOCATIONS") return "Locations";
  if (key === "CURRENT_SYSTEM") return "Current system";
  if (key === "SCHEDULING") return "Demo scheduling";
  return key || "Question";
}

export function parentOptionsForChild(
  roots: TreeQuestionNode[],
  childStepId: string
): FlatOption[] {
  function walk(node: TreeQuestionNode): FlatOption[] | null {
    for (const c of node.children) {
      if (c.question.step.id === childStepId) return node.options;
      const deeper = walk(c.question);
      if (deeper) return deeper;
    }
    return null;
  }
  for (const r of roots) {
    const hit = walk(r);
    if (hit) return hit;
  }
  return [];
}

export function childTriggerId(
  roots: TreeQuestionNode[],
  childStepId: string
): string | null {
  function walk(node: TreeQuestionNode): string | null | undefined {
    for (const c of node.children) {
      if (c.question.step.id === childStepId) return c.triggerOptionId;
      const deeper = walk(c.question);
      if (deeper !== undefined) return deeper;
    }
    return undefined;
  }
  for (const r of roots) {
    const hit = walk(r);
    if (hit !== undefined) return hit;
  }
  return null;
}

export { ANCHOR_KEYS, BUILTIN_KEYS, normKey, isTextLike };
