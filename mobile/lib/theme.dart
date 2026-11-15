/// Gruvbox dark palette, spacing, radii, type roles and Material theme.
///
/// The app is a warm terminal on a phone: deep espresso backgrounds, cream
/// text and one saturated accent.  Colour is reserved for state and the
/// floating surfaces, so the hierarchy stays readable in bright daylight.
library;

import 'package:material_ui/material_ui.dart';

abstract final class LoopColors {
  // Gruvbox dark, with the hard background as the canvas.
  static const bg0Hard = Color(0xFF1D2021);
  static const bg0 = Color(0xFF282828);
  static const bg0Soft = Color(0xFF32302F);
  static const bg1 = Color(0xFF3C3836);
  static const bg2 = Color(0xFF504945);
  static const bg3 = Color(0xFF665C54);
  static const bg4 = Color(0xFF7C6F64);
  static const fg0 = Color(0xFFFBF1C7);
  static const fg1 = Color(0xFFEBDBB2);
  static const fg2 = Color(0xFFD5C4A1);
  static const fg3 = Color(0xFFBDAE93);
  static const fg4 = Color(0xFFA89984);
  static const gray = Color(0xFF928374);
  static const red = Color(0xFFFB4934);
  static const green = Color(0xFFB8BB26);
  static const yellow = Color(0xFFFABD2F);
  static const blue = Color(0xFF83A598);
  static const purple = Color(0xFFD3869B);
  static const aqua = Color(0xFF8EC07C);
  static const orange = Color(0xFFFE8019);

  static const background = bg0Hard;
  static const surface = bg0;
  static const panel = bg0Soft;
  static const raised = bg1;
  static const line = bg1;
  static const lineStrong = bg2;
  static const faint = bg4;
  static const muted = fg4;
  static const body = fg2;
  static const strong = fg1;
  static const bright = fg0;
  static const accent = orange;
  static const accentSoft = yellow;
  static const ok = green;
  static const warn = yellow;
  static const error = red;
  static const info = blue;
}

abstract final class LoopSpace {
  static const xs = 4.0;
  static const sm = 8.0;
  static const md = 12.0;
  static const lg = 16.0;
  static const xl = 24.0;
  static const xxl = 32.0;
}

abstract final class LoopRadius {
  static const sm = 8.0;
  static const md = 12.0;
  static const lg = 18.0;
  static const xl = 24.0;
  static const pill = 999.0;
}

abstract final class LoopType {
  static const wordmark = TextStyle(
    color: LoopColors.bright,
    fontSize: 28,
    height: 1,
    fontWeight: FontWeight.w700,
    letterSpacing: -1.2,
  );
  static const hero = TextStyle(
    color: LoopColors.bright,
    fontSize: 22,
    height: 1.15,
    fontWeight: FontWeight.w700,
    letterSpacing: -0.4,
  );
  static const title = TextStyle(
    color: LoopColors.strong,
    fontSize: 15,
    height: 1.3,
    fontWeight: FontWeight.w600,
  );
  static const task = TextStyle(
    color: LoopColors.strong,
    fontSize: 14.5,
    height: 1.35,
    fontWeight: FontWeight.w500,
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
    fontWeight: FontWeight.w600,
    letterSpacing: 1.4,
  );
  static const caption = TextStyle(
    color: LoopColors.faint,
    fontSize: 10,
    height: 1.2,
    letterSpacing: 1.1,
  );
  static const mono = TextStyle(
    color: LoopColors.body,
    fontSize: 12,
    height: 1.5,
    fontFamily: 'monospace',
  );
}

String statusGlyph(String state) => switch (state) {
  'running' || 'starting' => '●',
  'complete' || 'done' => '✓',
  'interrupted' => '■',
  'error' || 'corrupt' => '✕',
  'queued' || 'waiting' => '○',
  _ => '·',
};

Color statusColor(String state) => switch (state) {
  'running' || 'starting' => LoopColors.accent,
  'complete' || 'done' => LoopColors.ok,
  'interrupted' => LoopColors.warn,
  'error' || 'corrupt' => LoopColors.error,
  'queued' || 'waiting' => LoopColors.info,
  _ => LoopColors.muted,
};

IconData statusIcon(String state) => switch (state) {
  'running' || 'starting' => Icons.bolt_rounded,
  'complete' || 'done' => Icons.check_circle_rounded,
  'interrupted' => Icons.pause_circle_filled_rounded,
  'error' || 'corrupt' => Icons.error_rounded,
  'queued' || 'waiting' => Icons.schedule_rounded,
  _ => Icons.circle_outlined,
};

ThemeData loopTheme() {
  const scheme = ColorScheme.dark(
    primary: LoopColors.accent,
    onPrimary: LoopColors.bg0Hard,
    secondary: LoopColors.aqua,
    onSecondary: LoopColors.bg0Hard,
    tertiary: LoopColors.purple,
    surface: LoopColors.surface,
    onSurface: LoopColors.body,
    error: LoopColors.error,
    onError: LoopColors.bg0Hard,
    outline: LoopColors.lineStrong,
  );
  final base = ThemeData(
    brightness: Brightness.dark,
    useMaterial3: true,
    fontFamily: 'monospace',
    colorScheme: scheme,
    scaffoldBackgroundColor: LoopColors.background,
    splashFactory: InkSparkle.splashFactory,
    visualDensity: VisualDensity.standard,
  );
  return base.copyWith(
    appBarTheme: const AppBarTheme(
      backgroundColor: LoopColors.background,
      surfaceTintColor: Colors.transparent,
      foregroundColor: LoopColors.strong,
      elevation: 0,
      scrolledUnderElevation: 0,
      centerTitle: false,
      toolbarHeight: 56,
      titleSpacing: 4,
      titleTextStyle: LoopType.title,
      iconTheme: IconThemeData(color: LoopColors.body, size: 22),
    ),
    dividerColor: LoopColors.line,
    dividerTheme: const DividerThemeData(
      color: LoopColors.line,
      thickness: 1,
      space: 1,
    ),
    highlightColor: const Color(0x14FE8019),
    splashColor: const Color(0x1AFE8019),
    textSelectionTheme: const TextSelectionThemeData(
      cursorColor: LoopColors.accent,
      selectionColor: Color(0x4DFE8019),
      selectionHandleColor: LoopColors.accent,
    ),
    textTheme: base.textTheme.apply(
      fontFamily: 'monospace',
      bodyColor: LoopColors.body,
      displayColor: LoopColors.strong,
    ),
    iconTheme: const IconThemeData(color: LoopColors.muted, size: 22),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: LoopColors.surface,
      isDense: true,
      contentPadding: const EdgeInsets.fromLTRB(14, 14, 14, 14),
      hintStyle: const TextStyle(color: LoopColors.faint, fontSize: 13),
      labelStyle: const TextStyle(color: LoopColors.muted, fontSize: 12),
      floatingLabelStyle: const TextStyle(
        color: LoopColors.accent,
        fontSize: 11,
      ),
      errorStyle: const TextStyle(color: LoopColors.error, fontSize: 11),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(LoopRadius.md),
        borderSide: const BorderSide(color: LoopColors.line),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(LoopRadius.md),
        borderSide: const BorderSide(color: LoopColors.line),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(LoopRadius.md),
        borderSide: const BorderSide(color: LoopColors.accent, width: 1.4),
      ),
      errorBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(LoopRadius.md),
        borderSide: const BorderSide(color: LoopColors.error),
      ),
      focusedErrorBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(LoopRadius.md),
        borderSide: const BorderSide(color: LoopColors.error, width: 1.4),
      ),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: LoopColors.accent,
        foregroundColor: LoopColors.bg0Hard,
        disabledBackgroundColor: LoopColors.line,
        disabledForegroundColor: LoopColors.faint,
        elevation: 0,
        minimumSize: const Size(0, 46),
        padding: const EdgeInsets.symmetric(horizontal: LoopSpace.lg),
        textStyle: const TextStyle(
          fontSize: 13,
          fontWeight: FontWeight.w700,
          letterSpacing: 0.3,
        ),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(LoopRadius.md),
        ),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: LoopColors.strong,
        disabledForegroundColor: LoopColors.faint,
        side: const BorderSide(color: LoopColors.lineStrong),
        minimumSize: const Size(0, 44),
        padding: const EdgeInsets.symmetric(horizontal: LoopSpace.lg),
        textStyle: const TextStyle(fontSize: 13, letterSpacing: 0.2),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(LoopRadius.md),
        ),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(
        foregroundColor: LoopColors.accent,
        disabledForegroundColor: LoopColors.faint,
        minimumSize: const Size(0, 34),
        padding: const EdgeInsets.symmetric(horizontal: LoopSpace.sm),
        textStyle: const TextStyle(fontSize: 12, letterSpacing: 0.2),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(LoopRadius.sm),
        ),
      ),
    ),
    listTileTheme: const ListTileThemeData(
      dense: true,
      contentPadding: EdgeInsets.symmetric(horizontal: LoopSpace.lg),
      minLeadingWidth: 0,
      iconColor: LoopColors.muted,
    ),
    snackBarTheme: SnackBarThemeData(
      backgroundColor: LoopColors.raised,
      contentTextStyle: const TextStyle(
        color: LoopColors.strong,
        fontFamily: 'monospace',
      ),
      behavior: SnackBarBehavior.floating,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(LoopRadius.md),
      ),
    ),
    bottomSheetTheme: const BottomSheetThemeData(
      backgroundColor: LoopColors.surface,
      surfaceTintColor: Colors.transparent,
      modalBackgroundColor: LoopColors.surface,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(
          top: Radius.circular(LoopRadius.xl),
        ),
      ),
    ),
    progressIndicatorTheme: const ProgressIndicatorThemeData(
      color: LoopColors.accent,
      linearTrackColor: LoopColors.line,
    ),
  );
}
