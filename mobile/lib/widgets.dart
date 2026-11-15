/// Shared chrome: one status line, hairlines, section rules and empty states.
library;

import 'package:material_ui/material_ui.dart';

import 'theme.dart';

class Hairline extends StatelessWidget {
  const Hairline({super.key, this.color = LoopColors.line, this.height = 1});

  final Color color;
  final double height;

  @override
  Widget build(BuildContext context) => Container(height: height, color: color);
}

class StatusBar extends StatelessWidget {
  const StatusBar({
    super.key,
    required this.state,
    required this.detail,
    this.trailing,
  });

  final String state;
  final String detail;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    final running = state == 'running';
    return Container(
      padding: const EdgeInsets.fromLTRB(
        LoopSpace.lg,
        LoopSpace.xs,
        LoopSpace.sm,
        LoopSpace.xs,
      ),
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: LoopColors.line)),
      ),
      child: SizedBox(
        height: 40,
        child: Row(
          children: [
            Text(
              statusGlyph(state),
              style: TextStyle(
                color: running ? LoopColors.accent : LoopColors.error,
                fontSize: 12,
                height: 1,
              ),
            ),
            const SizedBox(width: LoopSpace.sm),
            Flexible(
              child: Text(
                'daemon $state',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  color: running ? LoopColors.strong : LoopColors.error,
                  fontSize: 13,
                ),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                detail,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: LoopType.meta.copyWith(fontSize: 11),
              ),
            ),
            if (trailing != null) trailing!,
          ],
        ),
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
      decoration: BoxDecoration(
        color: LoopColors.error.withValues(alpha: 0.07),
        border: Border(
          left: BorderSide(
            color: LoopColors.error.withValues(alpha: 0.7),
            width: 2,
          ),
        ),
      ),
      padding: const EdgeInsets.fromLTRB(14, 8, LoopSpace.md, 8),
      child: Text(
        '✕ $text',
        style: const TextStyle(
          color: LoopColors.error,
          fontSize: 12,
          height: 1.35,
        ),
      ),
    );
  }
}

/// A muted label followed by a rule that spans the remaining width.
class SectionHeader extends StatelessWidget {
  const SectionHeader({super.key, required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(
        LoopSpace.lg,
        LoopSpace.xl - LoopSpace.xs,
        LoopSpace.lg,
        6,
      ),
      child: Row(
        children: [
          Text(label, style: LoopType.label),
          const SizedBox(width: 10),
          const Expanded(child: Hairline()),
        ],
      ),
    );
  }
}

class EmptyLine extends StatelessWidget {
  const EmptyLine({super.key, required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(
        LoopSpace.lg,
        LoopSpace.sm,
        LoopSpace.lg,
        10,
      ),
      child: Text(text, style: LoopType.meta.copyWith(color: LoopColors.faint)),
    );
  }
}
