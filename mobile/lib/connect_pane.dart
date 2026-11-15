/// Connection setup: warm Gruvbox login card for the local bridge.
library;

import 'package:material_ui/material_ui.dart';

import 'models.dart';
import 'theme.dart';
import 'widgets.dart';

class ConnectPane extends StatefulWidget {
  const ConnectPane({
    super.key,
    required this.initial,
    required this.error,
    required this.onConnect,
    this.onCancel,
  });

  final ConnectionSettings? initial;
  final String? error;
  final Future<bool> Function(String host, int port, String token) onConnect;
  final VoidCallback? onCancel;

  @override
  State<ConnectPane> createState() => _ConnectPaneState();
}

class _ConnectPaneState extends State<ConnectPane> {
  late final TextEditingController _host = TextEditingController(
    text: widget.initial?.host ?? '',
  );
  late final TextEditingController _port = TextEditingController(
    text: (widget.initial?.port ?? 8787).toString(),
  );
  late final TextEditingController _token = TextEditingController(
    text: widget.initial?.token ?? '',
  );
  bool _busy = false;
  bool _hidden = true;

  @override
  void dispose() {
    _host.dispose();
    _port.dispose();
    _token.dispose();
    super.dispose();
  }

  Future<void> _connect() async {
    final port = int.tryParse(_port.text.trim());
    if (port == null || port < 1 || port > 65535) {
      setState(() {});
      return;
    }
    setState(() => _busy = true);
    try {
      await widget.onConnect(_host.text.trim(), port, _token.text.trim());
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final portBad = _busy ? false : int.tryParse(_port.text.trim()) == null;
    return ListView(
      key: const Key('connect-list'),
      padding: const EdgeInsets.fromLTRB(20, 28, 20, 28),
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 52,
              height: 52,
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [LoopColors.accentSoft, LoopColors.accent],
                ),
                borderRadius: BorderRadius.circular(LoopRadius.lg),
                boxShadow: [
                  BoxShadow(
                    color: LoopColors.accent.withValues(alpha: 0.22),
                    blurRadius: 24,
                    offset: const Offset(0, 8),
                  ),
                ],
              ),
              alignment: Alignment.center,
              child: const Text(
                '>_',
                style: TextStyle(
                  color: LoopColors.bg0Hard,
                  fontSize: 16,
                  fontWeight: FontWeight.w800,
                  letterSpacing: -1,
                ),
              ),
            ),
            const SizedBox(width: LoopSpace.md),
            const Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('loop', style: LoopType.wordmark),
                  SizedBox(height: 3),
                  Text('local agent tasks', style: LoopType.meta),
                ],
              ),
            ),
            if (widget.onCancel != null)
              TextButton(
                key: const Key('cancel-connect'),
                onPressed: widget.onCancel,
                child: const Text('cancel'),
              ),
          ],
        ),
        const SizedBox(height: LoopSpace.lg),
        Row(
          children: [
            Container(
              padding: const EdgeInsets.fromLTRB(9, 5, 10, 5),
              decoration: BoxDecoration(
                color: LoopColors.aqua.withValues(alpha: 0.09),
                borderRadius: BorderRadius.circular(LoopRadius.pill),
                border: Border.all(
                  color: LoopColors.aqua.withValues(alpha: 0.3),
                ),
              ),
              child: const Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(
                    Icons.lock_outline_rounded,
                    size: 12,
                    color: LoopColors.aqua,
                  ),
                  SizedBox(width: 5),
                  Text(
                    'private network only',
                    style: TextStyle(
                      color: LoopColors.aqua,
                      fontSize: 10,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
        const SizedBox(height: LoopSpace.xl),
        LoopCard(
          color: LoopColors.surface,
          padding: const EdgeInsets.fromLTRB(18, 18, 18, 18),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Row(
                children: [
                  Icon(Icons.lan_outlined, size: 17, color: LoopColors.accent),
                  SizedBox(width: LoopSpace.sm),
                  Text('bridge', style: LoopType.label),
                ],
              ),
              const SizedBox(height: LoopSpace.lg),
              TextField(
                key: const Key('host-field'),
                controller: _host,
                keyboardType: TextInputType.url,
                textInputAction: TextInputAction.next,
                autocorrect: false,
                decoration: const InputDecoration(
                  labelText: 'host',
                  hintText: '192.168.1.10',
                  prefixIcon: Icon(Icons.dns_outlined, size: 18),
                ),
                onSubmitted: (_) => FocusScope.of(context).nextFocus(),
              ),
              const SizedBox(height: LoopSpace.md),
              TextField(
                key: const Key('port-field'),
                controller: _port,
                keyboardType: TextInputType.number,
                textInputAction: TextInputAction.next,
                onChanged: (_) => setState(() {}),
                decoration: InputDecoration(
                  labelText: 'port',
                  hintText: '8787',
                  prefixIcon: const Icon(Icons.tag_rounded, size: 18),
                  errorText: portBad ? '1..65535' : null,
                ),
                onSubmitted: (_) => FocusScope.of(context).nextFocus(),
              ),
              const SizedBox(height: LoopSpace.md),
              TextField(
                key: const Key('token-field'),
                controller: _token,
                obscureText: _hidden,
                autocorrect: false,
                enableSuggestions: false,
                textInputAction: TextInputAction.done,
                decoration: InputDecoration(
                  labelText: 'token',
                  prefixIcon: const Icon(Icons.key_rounded, size: 18),
                  suffixIcon: IconButton(
                    onPressed: () => setState(() => _hidden = !_hidden),
                    tooltip: _hidden ? 'show token' : 'hide token',
                    icon: Icon(
                      _hidden
                          ? Icons.visibility_outlined
                          : Icons.visibility_off_outlined,
                      size: 18,
                      color: LoopColors.muted,
                    ),
                  ),
                ),
                onSubmitted: (_) {
                  if (!_busy) _connect();
                },
              ),
              if (widget.error != null) ...[
                const SizedBox(height: LoopSpace.md),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(
                      Icons.error_outline_rounded,
                      color: LoopColors.error,
                      size: 16,
                    ),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Text(
                        widget.error!,
                        style: const TextStyle(
                          color: LoopColors.error,
                          fontSize: 12,
                          height: 1.4,
                        ),
                      ),
                    ),
                  ],
                ),
              ],
              const SizedBox(height: LoopSpace.lg),
              SizedBox(
                width: double.infinity,
                child: FilledButton.icon(
                  key: const Key('connect-button'),
                  onPressed: _busy ? null : _connect,
                  icon: _busy
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: LoopColors.bg0Hard,
                          ),
                        )
                      : const Icon(Icons.link_rounded, size: 19),
                  label: Text(_busy ? 'connecting' : 'connect'),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: LoopSpace.lg),
        LoopCard(
          color: LoopColors.bg0,
          padding: const EdgeInsets.fromLTRB(16, 14, 16, 14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Row(
                children: [
                  Icon(
                    Icons.terminal_rounded,
                    size: 16,
                    color: LoopColors.accentSoft,
                  ),
                  SizedBox(width: LoopSpace.sm),
                  Text('start the bridge', style: LoopType.label),
                ],
              ),
              const SizedBox(height: LoopSpace.sm),
              const Text(
                'python3 run.py server mobile start',
                style: TextStyle(
                  color: LoopColors.body,
                  fontSize: 11.5,
                  height: 1.6,
                ),
              ),
              const SizedBox(height: LoopSpace.xs),
              Text(
                'use the addr and token it prints. the bridge binds one private '
                'IP and requires the bearer token for every request.',
                style: LoopType.caption.copyWith(
                  color: LoopColors.faint,
                  height: 1.6,
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: LoopSpace.lg),
        const Center(
          child: Text('gruvbox · local only', style: LoopType.caption),
        ),
      ],
    );
  }
}
