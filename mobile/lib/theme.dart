/// Restrained, terminal-like palette, spacing and type roles.
///
/// One background, one hairline colour and one accent per state. Screens add
/// structure with rules and spacing, never with nested panels or cards.
library;

import 'package:material_ui/material_ui.dart';

abstract final class LoopColors {
  static const background = Color(0xFF0B0C0D);
  static const surface = Color(0xFF0F1113);
  static const panel = Color(0xFF14171A);
  static const line = Color(0xFF1F2327);
  static const lineStrong = Color(0xFF2B3036);
  static const faint = Color(0xFF5F6368);
  static const muted = Color(0xFF808080);
  static const body = Color(0xFFBCBCBC);
  static const strong = Color(0xFFD0D0D0);
  static const accent = Color(0xFF5F87AF);
  static const ok = Color(0xFF87AF87);
  static const warn = Color(0xFFD7AF5F);
  static const error = Color(0xFFD75F5F);
}

abstract final class LoopSpace {
  static const xs = 4.0;
  static const sm = 8.0;
  static const md = 12.0;
  static const lg = 16.0;
  static const xl = 24.0;
}

abstract final class LoopType {
  static const wordmark = TextStyle(
    color: LoopColors.strong,
    fontSize: 26,
    height: 1,
    letterSpacing: -0.5,
  );
  static const title = TextStyle(
    color: LoopColors.strong,
    fontSize: 14,
    height: 1.3,
  );
  static const task = TextStyle(
    color: LoopColors.strong,
    fontSize: 14.5,
    height: 1.35,
  );
  static const body = TextStyle(
    color: LoopColors.body,
    fontSize: 13,
    height: 1.5,
  );
  static const meta = TextStyle(
    color: LoopColors.muted,
    fontSize: 11.5,
    height: 1.4,
  );
  static const label = TextStyle(
    color: LoopColors.muted,
    fontSize: 10.5,
    height: 1.2,
    letterSpacing: 1.1,
  );
  static const caption = TextStyle(
    color: LoopColors.faint,
    fontSize: 10,
    height: 1.2,
    letterSpacing: 1.1,
  );
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
    onPrimary: LoopColors.background,
    secondary: LoopColors.ok,
    onSecondary: LoopColors.background,
    surface: LoopColors.background,
    onSurface: LoopColors.body,
    error: LoopColors.error,
    onError: LoopColors.background,
  );
  final base = ThemeData(
    brightness: Brightness.dark,
    useMaterial3: true,
    fontFamily: 'monospace',
    colorScheme: scheme,
    scaffoldBackgroundColor: LoopColors.background,
    splashFactory: NoSplash.splashFactory,
  );
  return base.copyWith(
    appBarTheme: const AppBarTheme(
      backgroundColor: LoopColors.background,
      surfaceTintColor: Colors.transparent,
      foregroundColor: LoopColors.strong,
      elevation: 0,
      scrolledUnderElevation: 0,
      centerTitle: false,
      toolbarHeight: 48,
      titleSpacing: 4,
      titleTextStyle: LoopType.title,
      iconTheme: IconThemeData(color: LoopColors.muted, size: 20),
      shape: Border(bottom: BorderSide(color: LoopColors.line)),
    ),
    dividerColor: LoopColors.line,
    dividerTheme: const DividerThemeData(
      color: LoopColors.line,
      thickness: 1,
      space: 1,
    ),
    highlightColor: const Color(0x0DFFFFFF),
    splashColor: Colors.transparent,
    textSelectionTheme: const TextSelectionThemeData(
      cursorColor: LoopColors.accent,
      selectionColor: Color(0x335F87AF),
      selectionHandleColor: LoopColors.accent,
    ),
    textTheme: base.textTheme.apply(
      fontFamily: 'monospace',
      bodyColor: LoopColors.body,
      displayColor: LoopColors.strong,
    ),
    inputDecorationTheme: const InputDecorationTheme(
      filled: false,
      isDense: true,
      contentPadding: EdgeInsets.only(top: 10, bottom: 10),
      hintStyle: TextStyle(color: LoopColors.faint, fontSize: 13),
      labelStyle: TextStyle(
        color: LoopColors.muted,
        fontSize: 12,
        letterSpacing: 0.3,
      ),
      floatingLabelStyle: TextStyle(color: LoopColors.muted, fontSize: 11),
      errorStyle: TextStyle(color: LoopColors.error, fontSize: 11),
      border: UnderlineInputBorder(
        borderSide: BorderSide(color: LoopColors.lineStrong),
      ),
      enabledBorder: UnderlineInputBorder(
        borderSide: BorderSide(color: LoopColors.lineStrong),
      ),
      focusedBorder: UnderlineInputBorder(
        borderSide: BorderSide(color: LoopColors.accent),
      ),
      errorBorder: UnderlineInputBorder(
        borderSide: BorderSide(color: LoopColors.error),
      ),
      focusedErrorBorder: UnderlineInputBorder(
        borderSide: BorderSide(color: LoopColors.error),
      ),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: LoopColors.accent,
        foregroundColor: LoopColors.background,
        disabledBackgroundColor: LoopColors.line,
        disabledForegroundColor: LoopColors.faint,
        elevation: 0,
        minimumSize: const Size(0, 40),
        padding: const EdgeInsets.symmetric(horizontal: LoopSpace.lg),
        textStyle: const TextStyle(fontSize: 13, letterSpacing: 0.3),
        shape: const RoundedRectangleBorder(borderRadius: BorderRadius.zero),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: LoopColors.strong,
        disabledForegroundColor: LoopColors.faint,
        side: const BorderSide(color: LoopColors.lineStrong),
        minimumSize: const Size(0, 40),
        padding: const EdgeInsets.symmetric(horizontal: LoopSpace.lg),
        textStyle: const TextStyle(fontSize: 13, letterSpacing: 0.3),
        shape: const RoundedRectangleBorder(borderRadius: BorderRadius.zero),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(
        foregroundColor: LoopColors.accent,
        disabledForegroundColor: LoopColors.faint,
        minimumSize: const Size(0, 32),
        padding: const EdgeInsets.symmetric(horizontal: LoopSpace.sm),
        textStyle: const TextStyle(fontSize: 12, letterSpacing: 0.2),
        shape: const RoundedRectangleBorder(borderRadius: BorderRadius.zero),
      ),
    ),
    listTileTheme: const ListTileThemeData(
      dense: true,
      contentPadding: EdgeInsets.symmetric(horizontal: LoopSpace.lg),
      minLeadingWidth: 0,
      iconColor: LoopColors.muted,
    ),
    snackBarTheme: const SnackBarThemeData(
      backgroundColor: LoopColors.panel,
      contentTextStyle: TextStyle(
        color: LoopColors.body,
        fontFamily: 'monospace',
      ),
      behavior: SnackBarBehavior.floating,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.zero),
    ),
  );
}
