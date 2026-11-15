/// Floating Gruvbox navigation: one rounded rail with an animated active pill.
library;

import 'package:material_ui/material_ui.dart';
import 'package:flutter/services.dart';

import 'theme.dart';

enum LoopTab { tasks, activity, workspace }

class FloatingNav extends StatelessWidget {
  const FloatingNav({
    super.key,
    required this.active,
    required this.onSelect,
    this.bottomInset = 0,
  });

  static const height = 68.0;

  final LoopTab active;
  final ValueChanged<LoopTab> onSelect;
  final double bottomInset;

  static const _items = [
    (LoopTab.tasks, 'tasks', Icons.checklist_rounded),
    (LoopTab.activity, 'activity', Icons.monitor_heart_outlined),
    (LoopTab.workspace, 'workspace', Icons.folder_open_rounded),
  ];

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.fromLTRB(
        LoopSpace.lg,
        LoopSpace.xs,
        LoopSpace.lg,
        LoopSpace.md + bottomInset,
      ),
      child: Container(
        key: const Key('bottom-nav'),
        height: height,
        padding: const EdgeInsets.all(6),
        decoration: BoxDecoration(
          color: LoopColors.panel.withValues(alpha: 0.97),
          borderRadius: BorderRadius.circular(LoopRadius.xl),
          border: Border.all(color: LoopColors.lineStrong),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.38),
              blurRadius: 26,
              offset: const Offset(0, 10),
            ),
            BoxShadow(
              color: LoopColors.accent.withValues(alpha: 0.06),
              blurRadius: 22,
              offset: const Offset(0, -2),
            ),
          ],
        ),
        child: Row(
          children: [
            for (final item in _items)
              Expanded(
                child: _NavItem(
                  key: Key('nav-${item.$2}'),
                  label: item.$2,
                  icon: item.$3,
                  selected: active == item.$1,
                  onTap: () {
                    if (active == item.$1) return;
                    HapticFeedback.selectionClick();
                    onSelect(item.$1);
                  },
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _NavItem extends StatelessWidget {
  const _NavItem({
    super.key,
    required this.label,
    required this.icon,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final IconData icon;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final color = selected ? LoopColors.accentSoft : LoopColors.muted;
    return Semantics(
      button: true,
      selected: selected,
      label: label,
      child: Material(
        color: Colors.transparent,
        borderRadius: BorderRadius.circular(LoopRadius.lg),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(LoopRadius.lg),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 220),
            curve: Curves.easeOutCubic,
            decoration: BoxDecoration(
              color: selected
                  ? LoopColors.accent.withValues(alpha: 0.13)
                  : Colors.transparent,
              borderRadius: BorderRadius.circular(LoopRadius.lg),
              border: Border.all(
                color: selected
                    ? LoopColors.accent.withValues(alpha: 0.26)
                    : Colors.transparent,
              ),
            ),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                AnimatedScale(
                  scale: selected ? 1.05 : 1,
                  duration: const Duration(milliseconds: 220),
                  curve: Curves.easeOutBack,
                  child: Icon(icon, size: 21, color: color),
                ),
                const SizedBox(height: 3),
                Text(
                  label,
                  maxLines: 1,
                  style: TextStyle(
                    color: color,
                    fontSize: 9.5,
                    height: 1,
                    fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
                    letterSpacing: 0.3,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
