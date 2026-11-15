/// Activity view: a Gruvbox timeline of current, queued and recent runs.
library;

import 'package:material_ui/material_ui.dart';

import 'models.dart';
import 'store.dart';
import 'task_rows.dart';
import 'theme.dart';
import 'widgets.dart';

class ActivityView extends StatelessWidget {
  const ActivityView({super.key, required this.store, required this.onOpenRun});

  final LoopStore store;
  final ValueChanged<String> onOpenRun;

  @override
  Widget build(BuildContext context) {
    final snapshot = store.snapshot;
    final rows = <({TaskItem item, bool live})>[
      if (snapshot.current != null) (item: snapshot.current!, live: true),
      for (final item in snapshot.queue) (item: item, live: false),
      for (final item in snapshot.done) (item: item, live: false),
    ];
    return RefreshIndicator(
      color: LoopColors.accent,
      backgroundColor: LoopColors.raised,
      onRefresh: store.refresh,
      child: ListView(
        key: const Key('activity-list'),
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(
          LoopSpace.lg,
          LoopSpace.sm,
          LoopSpace.lg,
          LoopSpace.lg,
        ),
        children: [
          const Text('recent tasks', style: LoopType.hero),
          const SizedBox(height: 4),
          Text(
            rows.isEmpty
                ? 'nothing has run yet'
                : '${rows.length} runs on this tree',
            style: LoopType.meta,
          ),
          const SizedBox(height: LoopSpace.md),
          Row(
            children: [
              _Stat(
                label: 'done',
                value: '${snapshot.done.length}',
                tone: LoopColors.ok,
                icon: Icons.check_circle_outline_rounded,
              ),
              const SizedBox(width: LoopSpace.sm),
              _Stat(
                label: 'queued',
                value: '${snapshot.queue.length}',
                tone: LoopColors.info,
                icon: Icons.schedule_rounded,
              ),
              const SizedBox(width: LoopSpace.sm),
              _Stat(
                label: 'spend',
                value: snapshot.totalCostLabel,
                tone: LoopColors.aqua,
                icon: Icons.ssid_chart_rounded,
              ),
            ],
          ),
          const SizedBox(height: LoopSpace.lg),
          if (rows.isEmpty)
            const EmptyState(
              icon: Icons.monitor_heart_outlined,
              title: 'quiet here',
              body:
                  'Queue a task from the tasks tab and its run will appear '
                  'here as the agent works.',
            )
          else
            for (var i = 0; i < rows.length; i++)
              _ActivityRow(
                key: Key('activity-${rows[i].item.id}'),
                item: rows[i].item,
                live: rows[i].live,
                last: i == rows.length - 1,
                onTap: rows[i].item.runId.isEmpty
                    ? null
                    : () => onOpenRun(rows[i].item.runId),
              ),
        ],
      ),
    );
  }
}

class _Stat extends StatelessWidget {
  const _Stat({
    required this.label,
    required this.value,
    required this.tone,
    required this.icon,
  });

  final String label;
  final String value;
  final Color tone;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.fromLTRB(11, 11, 11, 11),
        decoration: BoxDecoration(
          color: LoopColors.surface,
          borderRadius: BorderRadius.circular(LoopRadius.md),
          border: Border.all(color: LoopColors.line),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, size: 16, color: tone),
            const SizedBox(height: LoopSpace.sm),
            Text(
              value,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                color: LoopColors.strong,
                fontSize: 14,
                fontWeight: FontWeight.w700,
                height: 1.1,
              ),
            ),
            const SizedBox(height: 2),
            Text(label, style: LoopType.caption),
          ],
        ),
      ),
    );
  }
}

class _ActivityRow extends StatelessWidget {
  const _ActivityRow({
    super.key,
    required this.item,
    required this.live,
    required this.last,
    this.onTap,
  });

  final TaskItem item;
  final bool live;
  final bool last;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final tone = statusColor(item.state);
    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          SizedBox(
            width: 26,
            child: Column(
              children: [
                const SizedBox(height: 20),
                Container(
                  width: 18,
                  height: 18,
                  decoration: BoxDecoration(
                    color: tone.withValues(alpha: live ? 0.25 : 0.1),
                    shape: BoxShape.circle,
                    border: Border.all(color: tone.withValues(alpha: 0.55)),
                    boxShadow: live
                        ? [
                            BoxShadow(
                              color: tone.withValues(alpha: 0.35),
                              blurRadius: 12,
                            ),
                          ]
                        : null,
                  ),
                  child: Icon(statusIcon(item.state), color: tone, size: 11),
                ),
                if (!last)
                  Expanded(
                    child: Container(
                      width: 1,
                      margin: const EdgeInsets.symmetric(vertical: 3),
                      color: LoopColors.line,
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(width: LoopSpace.sm),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.only(bottom: LoopSpace.sm),
              child: LoopCard(
                onTap: onTap,
                color: live ? LoopColors.bg0Soft : LoopColors.surface,
                borderColor: live
                    ? LoopColors.accent.withValues(alpha: 0.45)
                    : LoopColors.line,
                padding: const EdgeInsets.fromLTRB(13, 12, 11, 12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Expanded(
                          child: Text(
                            item.task.isEmpty ? '(no task text)' : item.task,
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: LoopType.task,
                          ),
                        ),
                        if (onTap != null)
                          const Padding(
                            padding: EdgeInsets.only(left: 6),
                            child: Icon(
                              Icons.chevron_right_rounded,
                              size: 18,
                              color: LoopColors.faint,
                            ),
                          ),
                      ],
                    ),
                    const SizedBox(height: LoopSpace.sm),
                    Row(
                      children: [
                        StateChip(
                          state: item.state,
                          label: stateLabel(item.state),
                        ),
                        const Spacer(),
                        Text(
                          item.shortId,
                          style: LoopType.caption.copyWith(
                            color: LoopColors.faint,
                            letterSpacing: 0,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
