/// Compact task and queue rows: task text and status lead; ids, turns, cost
/// and finish stay in the run detail.
library;

import 'package:material_ui/material_ui.dart';

import 'models.dart';
import 'theme.dart';

class TaskRow extends StatelessWidget {
  const TaskRow({super.key, required this.item, this.onTap});

  final TaskItem item;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final color = statusColor(item.state);
    final label = stateLabel(item.state);
    final task = item.task.isEmpty ? '(no task text)' : item.task;
    return _RowShell(
      onTap: onTap,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.only(top: 2),
            child: Text(
              statusGlyph(item.state),
              style: TextStyle(color: color),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  task,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: LoopColors.strong,
                    fontSize: 15,
                    height: 1.35,
                  ),
                ),
                if (label != 'done') ...[
                  const SizedBox(height: 6),
                  Text(
                    label,
                    style: TextStyle(
                      color: color,
                      fontSize: 11,
                      letterSpacing: 0.7,
                    ),
                  ),
                ],
              ],
            ),
          ),
          if (onTap != null)
            const Padding(
              padding: EdgeInsets.only(left: 8, top: 2),
              child: Text('›', style: TextStyle(color: LoopColors.muted)),
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
          const Padding(
            padding: EdgeInsets.only(top: 2),
            child: Text('○', style: TextStyle(color: LoopColors.muted)),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              task,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                color: LoopColors.strong,
                fontSize: 15,
                height: 1.35,
              ),
            ),
          ),
        ],
      ),
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
  const _RowShell({required this.child, this.onTap});

  final Widget child;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final body = Container(
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 14),
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: LoopColors.line)),
      ),
      child: child,
    );
    return onTap == null ? body : InkWell(onTap: onTap, child: body);
  }
}
