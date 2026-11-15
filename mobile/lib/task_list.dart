/// Scrollable task board: workspace strip, summary, active, queue and done.
library;

import 'package:material_ui/material_ui.dart';

import 'models.dart';
import 'store.dart';
import 'task_rows.dart';
import 'theme.dart';
import 'widgets.dart';

class TaskList extends StatelessWidget {
  const TaskList({
    super.key,
    required this.store,
    required this.onBrowse,
    required this.onOpenRun,
  });

  final LoopStore store;
  final VoidCallback onBrowse;
  final ValueChanged<String> onOpenRun;

  @override
  Widget build(BuildContext context) {
    final snapshot = store.snapshot;
    return RefreshIndicator(
      color: LoopColors.accent,
      backgroundColor: LoopColors.raised,
      displacement: 30,
      onRefresh: store.refresh,
      child: ListView(
        key: const Key('task-list'),
        physics: const AlwaysScrollableScrollPhysics(),
        keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
        padding: const EdgeInsets.only(bottom: LoopSpace.lg),
        children: [
          _WorkspaceCard(store: store, onBrowse: onBrowse),
          _Overview(snapshot: snapshot),
          const SectionHeader(label: 'active'),
          if (snapshot.current == null)
            const EmptyLine(text: 'no active run')
          else
            TaskRow(
              key: Key('task-${snapshot.current!.runId}'),
              item: snapshot.current!,
              highlighted: true,
              onTap: () => onOpenRun(snapshot.current!.runId),
            ),
          if (snapshot.queue.isNotEmpty) ...[
            SectionHeader(label: 'queued', count: snapshot.queue.length),
            for (final item in snapshot.queue)
              QueueRow(key: Key('queue-${item.id}'), item: item),
          ],
          SectionHeader(label: 'done', count: snapshot.done.length),
          if (snapshot.done.isEmpty)
            const EmptyLine(text: 'no completed runs')
          else
            for (final item in snapshot.done)
              TaskRow(
                key: Key('task-${item.runId}'),
                item: item,
                onTap: () => onOpenRun(item.runId),
              ),
        ],
      ),
    );
  }
}

class _WorkspaceCard extends StatelessWidget {
  const _WorkspaceCard({required this.store, required this.onBrowse});

  final LoopStore store;
  final VoidCallback onBrowse;

  @override
  Widget build(BuildContext context) {
    final root = store.selectedRoot;
    final unset = root == null || root.isEmpty;
    return Padding(
      padding: const EdgeInsets.fromLTRB(
        LoopSpace.lg,
        LoopSpace.sm,
        LoopSpace.lg,
        0,
      ),
      child: LoopCard(
        key: const Key('workspace-card'),
        padding: const EdgeInsets.fromLTRB(13, 12, 10, 12),
        color: LoopColors.surface,
        borderColor: unset
            ? LoopColors.warn.withValues(alpha: 0.42)
            : LoopColors.line,
        child: Row(
          children: [
            Container(
              width: 36,
              height: 36,
              decoration: BoxDecoration(
                color: (unset ? LoopColors.warn : LoopColors.aqua).withValues(
                  alpha: 0.1,
                ),
                borderRadius: BorderRadius.circular(LoopRadius.md),
              ),
              child: Icon(
                Icons.folder_rounded,
                color: unset ? LoopColors.warn : LoopColors.aqua,
                size: 19,
              ),
            ),
            const SizedBox(width: LoopSpace.md),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('workspace', style: LoopType.label),
                  const SizedBox(height: 3),
                  Text(
                    unset ? 'not selected' : root,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      color: unset ? LoopColors.warn : LoopColors.body,
                      fontSize: 12,
                      height: 1.3,
                    ),
                  ),
                ],
              ),
            ),
            TextButton(
              key: const Key('browse-button'),
              onPressed: store.loadingDirs ? null : onBrowse,
              child: Text(store.loadingDirs ? '…' : 'browse'),
            ),
          ],
        ),
      ),
    );
  }
}

class _Overview extends StatelessWidget {
  const _Overview({required this.snapshot});

  final Snapshot snapshot;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(
        LoopSpace.lg,
        LoopSpace.sm,
        LoopSpace.lg,
        0,
      ),
      child: Row(
        children: [
          _Metric(
            label: 'running',
            value: snapshot.current == null ? '0' : '1',
            tone: LoopColors.accent,
          ),
          const SizedBox(width: LoopSpace.sm),
          _Metric(
            label: 'queued',
            value: '${snapshot.queue.length}',
            tone: LoopColors.info,
          ),
          const SizedBox(width: LoopSpace.sm),
          _Metric(
            label: 'cost',
            value: snapshot.totalCostLabel,
            tone: LoopColors.aqua,
          ),
        ],
      ),
    );
  }
}

class _Metric extends StatelessWidget {
  const _Metric({required this.label, required this.value, required this.tone});

  final String label;
  final String value;
  final Color tone;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.fromLTRB(12, 10, 12, 10),
        decoration: BoxDecoration(
          color: LoopColors.surface,
          borderRadius: BorderRadius.circular(LoopRadius.md),
          border: Border.all(color: LoopColors.line),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label.toUpperCase(), style: LoopType.caption),
            const SizedBox(height: 4),
            Text(
              value,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                color: tone,
                fontSize: 14,
                fontWeight: FontWeight.w700,
                height: 1.2,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
