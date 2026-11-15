/// Restrained, terminal-like palette shared by every screen.
library;

import 'package:material_ui/material_ui.dart';

abstract final class LoopColors {
  static const background = Color(0xFF0B0C0D);
  static const panel = Color(0xFF121417);
  static const line = Color(0xFF23272B);
  static const muted = Color(0xFF808080);
  static const body = Color(0xFFBCBCBC);
  static const strong = Color(0xFFD0D0D0);
  static const accent = Color(0xFF5F87AF);
  static const ok = Color(0xFF87AF87);
  static const warn = Color(0xFFD7AF5F);
  static const error = Color(0xFFD75F5F);
}

String statusGlyph(String state) => switch (state) {
      'running' => '●',
      'complete' || 'done' => '✓',
      'interrupted' => '■',
      'error' || 'corrupt' => '✕',
      'queued' || 'waiting' => '○',
      _ => '·',
    };

Color statusColor(String state) => switch (state) {
      'running' => LoopColors.accent,
      'complete' || 'done' => LoopColors.ok,
      'interrupted' => LoopColors.warn,
      'error' || 'corrupt' => LoopColors.error,
      _ => LoopColors.muted,
    };

ThemeData loopTheme() {
  const scheme = ColorScheme.dark(
    primary: LoopColors.accent,
    secondary: LoopColors.ok,
    surface: LoopColors.panel,
    onSurface: LoopColors.body,
    error: LoopColors.error,
    onError: LoopColors.background,
    onPrimary: LoopColors.background,
    onSecondary: LoopColors.background,
  );
  final base = ThemeData(
    brightness: Brightness.dark,
    useMaterial3: true,
    fontFamily: 'monospace',
    colorScheme: scheme,
    scaffoldBackgroundColor: LoopColors.background,
  );
  return base.copyWith(
    appBarTheme: const AppBarTheme(
      backgroundColor: LoopColors.background,
      foregroundColor: LoopColors.strong,
      elevation: 0,
      centerTitle: false,
    ),
    dividerColor: LoopColors.line,
    textTheme: base.textTheme.apply(
      fontFamily: 'monospace',
      bodyColor: LoopColors.body,
      displayColor: LoopColors.strong,
    ),
    inputDecorationTheme: const InputDecorationTheme(
      filled: true,
      fillColor: LoopColors.panel,
      isDense: true,
      hintStyle: const TextStyle(color: LoopColors.muted),
      labelStyle: const TextStyle(color: LoopColors.muted),
      enabledBorder: const OutlineInputBorder(
        borderSide: BorderSide(color: LoopColors.line),
        borderRadius: BorderRadius.zero,
      ),
      focusedBorder: const OutlineInputBorder(
        borderSide: BorderSide(color: LoopColors.accent),
        borderRadius: BorderRadius.zero,
      ),
      errorBorder: const OutlineInputBorder(
        borderSide: BorderSide(color: LoopColors.error),
        borderRadius: BorderRadius.zero,
      ),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: LoopColors.accent,
        foregroundColor: LoopColors.background,
        shape: const RoundedRectangleBorder(borderRadius: BorderRadius.zero),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: LoopColors.strong,
        side: const BorderSide(color: LoopColors.line),
        shape: const RoundedRectangleBorder(borderRadius: BorderRadius.zero),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(foregroundColor: LoopColors.accent),
    ),
    listTileTheme: const ListTileThemeData(
      dense: true,
      contentPadding: EdgeInsets.symmetric(horizontal: 12),
      minLeadingWidth: 0,
    ),
    snackBarTheme: const SnackBarThemeData(
      backgroundColor: LoopColors.panel,
      contentTextStyle: TextStyle(color: LoopColors.body, fontFamily: 'monospace'),
    ),
  );
}
