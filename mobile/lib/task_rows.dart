/// Rounded task and queue rows: task text and state lead; metadata stays in
/// the run detail.
library;

import 'package:material_ui/material_ui.dart';

import 'models.dart';
import 'theme.dart';
import 'widgets.dart';

class TaskRow extends StatelessWidget {
  const TaskRow({
    super.key,
    required this.item,
    this.onTap,
    this.highlighted = false,
  });

  final TaskItem item;
  final VoidCallback? onTap;
  final bool highlighted;

  @override
  Widget build(BuildContext context) {
    final color = statusColor(item.state);
    final label = stateLabel(item.state);
    final task = item.task.isEmpty ? '(no task text)' : item.task;
    return _RowShell(
      onTap: onTap,
      highlighted: highlighted,
      accent: highlighted ? LoopColors.accent : LoopColors.line,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _StatusTile(state: item.state, tone: color),
          const SizedBox(width: LoopSpace.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  task,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: LoopType.task,
                ),
                if (label != 'done') ...[
                  const SizedBox(height: LoopSpace.sm),
                  StateChip(state: item.state, label: label),
                ] else ...[
                  const SizedBox(height: LoopSpace.sm),
                  Text(
                    item.finish.isEmpty ? 'finished' : item.finish,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: LoopType.caption.copyWith(
                      color: LoopColors.faint,
                      letterSpacing: 0.4,
                    ),
                  ),
                ],
              ],
            ),
          ),
          if (onTap != null)
            const Padding(
              padding: EdgeInsets.only(left: LoopSpace.sm, top: 10),
              child: Icon(
                Icons.chevron_right_rounded,
                color: LoopColors.faint,
                size: 20,
              ),
            ),
        ],
      ),
    );
  }
}

class QueueRow extends StatelessWidget {
  const QueueRow({super.key, required this.item});

  final TaskItem item;

  @override
  Widget build(BuildContext context) {
    final task = item.task.isEmpty ? '(no task text)' : item.task;
    return _RowShell(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _StatusTile(state: 'queued', tone: LoopColors.info),
          const SizedBox(width: LoopSpace.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  task,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: LoopType.task.copyWith(color: LoopColors.body),
                ),
                const SizedBox(height: LoopSpace.sm),
                const StateChip(state: 'queued', label: 'waiting'),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _StatusTile extends StatelessWidget {
  const _StatusTile({required this.state, required this.tone});

  final String state;
  final Color tone;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 34,
      height: 34,
      decoration: BoxDecoration(
        color: tone.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(LoopRadius.md),
        border: Border.all(color: tone.withValues(alpha: 0.22)),
      ),
      child: Icon(statusIcon(state), color: tone, size: 18),
    );
  }
}

String stateLabel(String state) => switch (state) {
  'complete' || 'done' => 'done',
  'interrupted' => 'interrupted',
  'error' || 'corrupt' => 'error',
  'queued' || 'waiting' => 'queued',
  'running' => 'running',
  _ => state,
};

class _RowShell extends StatelessWidget {
  const _RowShell({
    required this.child,
    this.onTap,
    this.highlighted = false,
    this.accent = LoopColors.line,
  });

  final Widget child;
  final VoidCallback? onTap;
  final bool highlighted;
  final Color accent;

  @override
  Widget build(BuildContext context) {
    final body = Container(
      margin: const EdgeInsets.fromLTRB(
        LoopSpace.lg,
        0,
        LoopSpace.lg,
        LoopSpace.sm,
      ),
      padding: const EdgeInsets.fromLTRB(12, 13, 12, 13),
      decoration: BoxDecoration(
        color: highlighted ? LoopColors.bg0Soft : LoopColors.surface,
        borderRadius: BorderRadius.circular(LoopRadius.lg),
        border: Border.all(
          color: highlighted ? accent.withValues(alpha: 0.55) : LoopColors.line,
          width: highlighted ? 1.3 : 1,
        ),
        boxShadow: highlighted
            ? [
                BoxShadow(
                  color: LoopColors.accent.withValues(alpha: 0.1),
                  blurRadius: 22,
                  offset: const Offset(0, 8),
                ),
              ]
            : null,
      ),
      child: child,
    );
    if (onTap == null) return body;
    return Padding(
      padding: EdgeInsets.zero,
      child: Material(
        color: Colors.transparent,
        borderRadius: BorderRadius.circular(LoopRadius.lg),
        clipBehavior: Clip.antiAlias,
        child: InkWell(onTap: onTap, child: body),
      ),
    );
  }
}
