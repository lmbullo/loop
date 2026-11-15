/// Small shared rows that keep every screen on the same terminal-like grid.
library;

import 'package:material_ui/material_ui.dart';

import 'models.dart';
import 'theme.dart';

class StatusBar extends StatelessWidget {
  const StatusBar({super.key, required this.state, required this.detail, this.trailing});

  final String state;
  final String detail;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    final color = state == 'running' ? LoopColors.ok : LoopColors.error;
    return Container(
      padding: const EdgeInsets.fromLTRB(12, 10, 8, 8),
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: LoopColors.line)),
      ),
      child: Row(
        children: [
          Text(statusGlyph(state), style: TextStyle(color: color)),
          const SizedBox(width: 8),
          Text('daemon $state',
              style: const TextStyle(color: LoopColors.strong)),
          const SizedBox(width: 8),
          Expanded(
            child: Text(detail,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(color: LoopColors.muted, fontSize: 12)),
          ),
          if (trailing != null) trailing!,
        ],
      ),
    );
  }
}

class ErrorBanner extends StatelessWidget {
  const ErrorBanner({super.key, required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      color: LoopColors.error.withValues(alpha: 0.12),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      child: Text('✕ $text',
          style: const TextStyle(color: LoopColors.error, fontSize: 12)),
    );
  }
}

class SectionHeader extends StatelessWidget {
  const SectionHeader({super.key, required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 16, 12, 6),
      child: Text(label, style: const TextStyle(color: LoopColors.muted)),
    );
  }
}

class EmptyLine extends StatelessWidget {
  const EmptyLine({super.key, required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 4, 12, 4),
      child: Text(text, style: const TextStyle(color: LoopColors.muted)),
    );
  }
}

class TaskRow extends StatelessWidget {
  const TaskRow({super.key, required this.item, this.onTap});

  final TaskItem item;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final color = statusColor(item.state);
    final meta = [
      'id=${item.shortId}',
      'turns=${item.turns}',
      'cost=${item.costLabel}',
      if (item.finish.isNotEmpty) 'finish=${item.finish}',
    ].join(' · ');
    return _Row(
      onTap: onTap,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(statusGlyph(item.state), style: TextStyle(color: color)),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(meta, style: const TextStyle(color: LoopColors.muted, fontSize: 12)),
                const SizedBox(height: 2),
                Text(item.task.isEmpty ? '(no task text)' : item.task,
                    style: const TextStyle(color: LoopColors.body)),
                if (item.detail.isNotEmpty)
                  Text(item.detail,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(color: LoopColors.warn, fontSize: 12)),
              ],
            ),
          ),
          if (onTap != null)
            const Padding(
              padding: EdgeInsets.only(left: 8),
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
    return _Row(
      child: Row(
        children: [
          const Text('○ ', style: TextStyle(color: LoopColors.muted)),
          SizedBox(
            width: 72,
            child: Text(item.id,
                style: const TextStyle(color: LoopColors.muted, fontSize: 12)),
          ),
          Expanded(
            child: Text(item.task.isEmpty ? '(no task text)' : item.task,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(color: LoopColors.body)),
          ),
        ],
      ),
    );
  }
}

class _Row extends StatelessWidget {
  const _Row({required this.child, this.onTap});

  final Widget child;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final body = Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
      child: child,
    );
    return DecoratedBox(
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: LoopColors.line)),
      ),
      child: onTap == null
          ? body
          : InkWell(onTap: onTap, child: body),
    );
  }
}
