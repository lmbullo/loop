/// Client-side state derived from server responses.
///
/// The store never invents a task, a run id or a log entry.  It polls the
/// server snapshot, keeps the selected workspace, and loads one active run log
/// while the run view is open.  UI widgets read this object and render it.
library;

import 'dart:async';

import 'package:flutter/foundation.dart';

import 'api.dart';
import 'models.dart';

typedef ApiFactory = LoopApi Function(ConnectionSettings settings);

class LoopStore extends ChangeNotifier {
  LoopStore({
    ApiFactory? apiFactory,
    this.pollInterval = const Duration(milliseconds: 1200),
    ConnectionSettings? saved,
  }) : _apiFactory = apiFactory ?? ((settings) => HttpLoopApi(settings)) {
    settings = saved;
  }

  final ApiFactory _apiFactory;
  final Duration pollInterval;

  ConnectionSettings? settings;
  LoopApi? _api;
  Snapshot snapshot = Snapshot.empty;
  DirListing listing = DirListing.empty;
  RunLog? runLog;
  String? activeRunId;
  String? selectedRoot;
  String? error;
  bool online = false;
  bool connecting = false;
  bool submitting = false;
  bool loadingDirs = false;
  bool loadingLog = false;

  Timer? _timer;
  bool _ticking = false;
  bool _disposed = false;

  bool get connected => settings != null && _api != null;
  bool get canSubmit =>
      connected && !submitting && selectedRoot != null && selectedRoot!.isNotEmpty;
  String get statusState => online ? 'running' : (connected ? 'offline' : 'detached');
  String get statusDetail => error ?? (online ? 'local network' : 'not connected');

  void _notify() {
    if (!_disposed) notifyListeners();
  }

  Future<bool> connect(String host, int port, String token) async {
    if (connecting) return false;
    connecting = true;
    error = null;
    _notify();
    try {
      final normalized = await validateLocalHost(host);
      if (token.trim().isEmpty) {
        throw const LoopApiException(ApiFailure.auth, 'token is required');
      }
      _stopTimer();
      _api?.close();
      settings = ConnectionSettings(
          host: normalized, port: port, token: token.trim());
      _api = _apiFactory(settings!);
      snapshot = Snapshot.empty;
      listing = DirListing.empty;
      selectedRoot = null;
      runLog = null;
      activeRunId = null;
      await browse(null, notify: false);
      await refresh(notify: false);
      _startTimer();
      return online;
    } catch (failure) {
      _setFailure(failure);
      return false;
    } finally {
      connecting = false;
      _notify();
    }
  }

  void disconnect() {
    _stopTimer();
    _api?.close();
    _api = null;
    settings = null;
    snapshot = Snapshot.empty;
    listing = DirListing.empty;
    runLog = null;
    activeRunId = null;
    selectedRoot = null;
    online = false;
    error = null;
    _notify();
  }

  void _startTimer() {
    _stopTimer();
    _timer = Timer.periodic(pollInterval, (_) => _tick());
  }

  void _stopTimer() {
    _timer?.cancel();
    _timer = null;
  }

  Future<void> _tick() async {
    if (_ticking || _api == null) return;
    _ticking = true;
    try {
      await refresh(notify: false);
      final id = activeRunId;
      if (id != null && (runLog == null || !runLog!.terminal)) {
        await refreshActiveRun(notify: false);
      }
    } finally {
      _ticking = false;
      _notify();
    }
  }

  Future<void> refresh({bool notify = true}) async {
    final api = _api;
    if (api == null) return;
    try {
      snapshot = Snapshot.fromJson(await api.snapshot());
      online = true;
      error = null;
      if (selectedRoot == null && listing.roots.isNotEmpty) {
        selectedRoot = listing.roots.first.path;
      }
    } catch (failure) {
      _setFailure(failure);
    }
    if (notify) _notify();
  }

  Future<void> browse(String? path, {bool notify = true}) async {
    final api = _api;
    if (api == null) return;
    loadingDirs = true;
    if (notify) _notify();
    try {
      listing = DirListing.fromJson(await api.dirs(path));
      if (selectedRoot == null && listing.roots.isNotEmpty) {
        selectedRoot = listing.roots.first.path;
      }
    } catch (failure) {
      _setFailure(failure);
    } finally {
      loadingDirs = false;
      if (notify) _notify();
    }
  }

  void selectRoot(String path) {
    selectedRoot = path;
    _notify();
  }

  Future<bool> submitTask(String text) async {
    final api = _api;
    final root = selectedRoot;
    final task = text.trim();
    if (api == null || root == null || root.isEmpty) {
      error = 'select a workspace before submitting';
      _notify();
      return false;
    }
    if (task.isEmpty) {
      error = 'task is empty';
      _notify();
      return false;
    }
    submitting = true;
    error = null;
    _notify();
    try {
      await api.enqueue(task, root);
      await refresh(notify: false);
      return true;
    } catch (failure) {
      _setFailure(failure);
      return false;
    } finally {
      submitting = false;
      _notify();
    }
  }

  Future<void> watchRun(String runId) async {
    activeRunId = runId;
    runLog = null;
    await _loadRun(runId);
  }

  Future<void> refreshActiveRun({bool notify = true}) async {
    final id = activeRunId;
    if (id != null) await _loadRun(id, notify: notify);
  }

  void unwatchRun([String? runId]) {
    if (runId != null && activeRunId != runId) return;
    activeRunId = null;
    runLog = null;
    _notify();
  }

  Future<void> _loadRun(String runId, {bool notify = true}) async {
    final api = _api;
    if (api == null) return;
    loadingLog = true;
    if (notify) _notify();
    try {
      final parsed = RunLog.fromJson(await api.runLog(runId));
      if (activeRunId == runId) runLog = parsed;
    } catch (failure) {
      _setFailure(failure);
    } finally {
      loadingLog = false;
      if (notify) _notify();
    }
  }

  void _setFailure(Object failure) {
    online = false;
    if (failure is LoopApiException) {
      error = failure.message;
    } else {
      error = failure.toString();
    }
  }

  @override
  void dispose() {
    _disposed = true;
    _stopTimer();
    _api?.close();
    super.dispose();
  }
}
