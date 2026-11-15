/// Shared Gruvbox chrome: header, pills, cards, hairlines and empty states.
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

/// Warm radial bloom behind the app; one uninterrupted canvas, no panels.
class LoopBackdrop extends StatelessWidget {
  const LoopBackdrop({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: const BoxDecoration(
        gradient: RadialGradient(
          center: Alignment(0.85, -0.95),
          radius: 1.25,
          colors: [Color(0x2EFE8019), Color(0x0AD3869B), LoopColors.background],
          stops: [0, 0.42, 1],
        ),
      ),
      child: child,
    );
  }
}

class LoopHeader extends StatelessWidget {
  const LoopHeader({
    super.key,
    required this.state,
    required this.detail,
    this.host,
    this.onConfig,
  });

  final String state;
  final String detail;
  final String? host;
  final VoidCallback? onConfig;

  @override
  Widget build(BuildContext context) {
    final online = state == 'running' || state == 'starting';
    final tone = online ? LoopColors.ok : LoopColors.error;
    return Padding(
      padding: const EdgeInsets.fromLTRB(
        LoopSpace.lg,
        LoopSpace.sm,
        LoopSpace.md,
        LoopSpace.xs,
      ),
      child: Row(
        children: [
          Container(
            width: 42,
            height: 42,
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [LoopColors.accentSoft, LoopColors.accent],
              ),
              borderRadius: BorderRadius.circular(LoopRadius.md),
              boxShadow: [
                BoxShadow(
                  color: LoopColors.accent.withValues(alpha: 0.24),
                  blurRadius: 18,
                  offset: const Offset(0, 6),
                ),
              ],
            ),
            alignment: Alignment.center,
            child: const Text(
              '>_',
              style: TextStyle(
                color: LoopColors.bg0Hard,
                fontSize: 13,
                fontWeight: FontWeight.w800,
                letterSpacing: -1,
              ),
            ),
          ),
          const SizedBox(width: LoopSpace.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('loop', style: LoopType.wordmark),
                const SizedBox(height: 2),
                Text(
                  host == null || host!.isEmpty ? 'local agent tasks' : host!,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: LoopType.caption.copyWith(color: LoopColors.faint),
                ),
              ],
            ),
          ),
          _ConnectionChip(state: state, detail: detail, tone: tone),
          if (onConfig != null)
            IconButton(
              key: const Key('config-button'),
              onPressed: onConfig,
              tooltip: 'connection settings',
              icon: const Icon(Icons.tune_rounded, size: 20),
              color: LoopColors.muted,
            ),
        ],
      ),
    );
  }
}

class _ConnectionChip extends StatelessWidget {
  const _ConnectionChip({
    required this.state,
    required this.detail,
    required this.tone,
  });

  final String state;
  final String detail;
  final Color tone;

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: detail,
      child: Container(
        padding: const EdgeInsets.fromLTRB(9, 6, 10, 6),
        decoration: BoxDecoration(
          color: tone.withValues(alpha: 0.1),
          borderRadius: BorderRadius.circular(LoopRadius.pill),
          border: Border.all(color: tone.withValues(alpha: 0.35)),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 6,
              height: 6,
              decoration: BoxDecoration(color: tone, shape: BoxShape.circle),
            ),
            const SizedBox(width: 6),
            Text(
              'daemon $state',
              style: TextStyle(
                color: tone,
                fontSize: 10.5,
                fontWeight: FontWeight.w600,
                letterSpacing: 0.2,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class SectionHeader extends StatelessWidget {
  const SectionHeader({
    super.key,
    required this.label,
    this.count,
    this.trailing,
  });

  final String label;
  final int? count;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(
        LoopSpace.lg,
        LoopSpace.lg,
        LoopSpace.lg,
        LoopSpace.sm,
      ),
      child: Row(
        children: [
          Text(label.toUpperCase(), style: LoopType.label),
          if (count != null) ...[
            const SizedBox(width: LoopSpace.sm),
            CountBadge(value: count!),
          ],
          const SizedBox(width: LoopSpace.md),
          const Expanded(child: Hairline(color: LoopColors.line)),
          if (trailing != null) ...[
            const SizedBox(width: LoopSpace.sm),
            trailing!,
          ],
        ],
      ),
    );
  }
}

class CountBadge extends StatelessWidget {
  const CountBadge({super.key, required this.value, this.tone});

  final int value;
  final Color? tone;

  @override
  Widget build(BuildContext context) {
    final color = tone ?? LoopColors.muted;
    return Container(
      constraints: const BoxConstraints(minWidth: 22),
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(LoopRadius.pill),
        border: Border.all(color: color.withValues(alpha: 0.24)),
      ),
      alignment: Alignment.center,
      child: Text(
        '$value',
        style: TextStyle(
          color: color,
          fontSize: 10,
          fontWeight: FontWeight.w700,
          height: 1.3,
        ),
      ),
    );
  }
}

class StateChip extends StatelessWidget {
  const StateChip({super.key, required this.state, this.label});

  final String state;
  final String? label;

  @override
  Widget build(BuildContext context) {
    final color = statusColor(state);
    return Container(
      padding: const EdgeInsets.fromLTRB(8, 4, 9, 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(LoopRadius.pill),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(statusIcon(state), color: color, size: 12),
          const SizedBox(width: 5),
          Text(
            label ?? state,
            style: TextStyle(
              color: color,
              fontSize: 10,
              fontWeight: FontWeight.w600,
              letterSpacing: 0.2,
            ),
          ),
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
      margin: const EdgeInsets.fromLTRB(
        LoopSpace.lg,
        LoopSpace.xs,
        LoopSpace.lg,
        LoopSpace.xs,
      ),
      padding: const EdgeInsets.fromLTRB(12, 10, 12, 10),
      decoration: BoxDecoration(
        color: LoopColors.error.withValues(alpha: 0.09),
        borderRadius: BorderRadius.circular(LoopRadius.md),
        border: Border.all(color: LoopColors.error.withValues(alpha: 0.35)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(
            Icons.error_outline_rounded,
            color: LoopColors.error,
            size: 17,
          ),
          const SizedBox(width: LoopSpace.sm),
          Expanded(
            child: Text(
              text,
              style: const TextStyle(
                color: LoopColors.error,
                fontSize: 12,
                height: 1.4,
              ),
            ),
          ),
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
        LoopSpace.sm,
      ),
      child: Text(text, style: LoopType.meta.copyWith(color: LoopColors.faint)),
    );
  }
}

class EmptyState extends StatelessWidget {
  const EmptyState({
    super.key,
    required this.icon,
    required this.title,
    required this.body,
  });

  final IconData icon;
  final String title;
  final String body;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(
        LoopSpace.xl,
        LoopSpace.xxl,
        LoopSpace.xl,
        LoopSpace.xl,
      ),
      child: Column(
        children: [
          Container(
            width: 52,
            height: 52,
            decoration: BoxDecoration(
              color: LoopColors.panel,
              borderRadius: BorderRadius.circular(LoopRadius.lg),
              border: Border.all(color: LoopColors.line),
            ),
            child: Icon(icon, color: LoopColors.faint, size: 24),
          ),
          const SizedBox(height: LoopSpace.md),
          Text(title, style: LoopType.title, textAlign: TextAlign.center),
          const SizedBox(height: LoopSpace.xs),
          Text(
            body,
            textAlign: TextAlign.center,
            style: LoopType.meta.copyWith(color: LoopColors.faint),
          ),
        ],
      ),
    );
  }
}

/// A rounded Gruvbox surface with a hairline edge and one soft shadow.
class LoopCard extends StatelessWidget {
  const LoopCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(LoopSpace.lg),
    this.color = LoopColors.surface,
    this.borderColor = LoopColors.line,
    this.onTap,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;
  final Color color;
  final Color borderColor;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final body = Container(
      padding: padding,
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(LoopRadius.lg),
        border: Border.all(color: borderColor),
      ),
      child: child,
    );
    if (onTap == null) return body;
    return Material(
      color: Colors.transparent,
      borderRadius: BorderRadius.circular(LoopRadius.lg),
      clipBehavior: Clip.antiAlias,
      child: InkWell(onTap: onTap, child: body),
    );
  }
}
