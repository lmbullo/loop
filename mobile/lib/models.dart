/// Pure JSON models for the loop mobile protocol.
///
/// The server is authoritative: every field here is parsed from one of its
/// responses.  Missing fields fall back to display-safe values so an older
/// daemon cannot crash the UI.
library;

Map<String, dynamic> asMap(Object? value) =>
    value is Map ? Map<String, dynamic>.from(value) : <String, dynamic>{};

List<dynamic> asList(Object? value) => value is List ? value : const [];

String asString(Object? value, [String fallback = '']) =>
    value == null ? fallback : value.toString();

int asInt(Object? value, [int fallback = 0]) {
  if (value is int) return value;
  if (value is num) return value.toInt();
  return int.tryParse(asString(value)) ?? fallback;
}

double? asDouble(Object? value) {
  if (value is num) return value.toDouble();
  return double.tryParse(asString(value));
}

bool asBool(Object? value) => value == true;

class ConnectionSettings {
  const ConnectionSettings({
    required this.host,
    required this.port,
    required this.token,
  });

  final String host;
  final int port;
  final String token;

  String get label => port == 80 ? host : '$host:$port';

  ConnectionSettings copyWith({String? host, int? port, String? token}) =>
      ConnectionSettings(
        host: host ?? this.host,
        port: port ?? this.port,
        token: token ?? this.token,
      );
}

class TaskItem {
  const TaskItem({
    required this.id,
    required this.runId,
    required this.task,
    required this.state,
    required this.turns,
    this.cost,
    this.finish = '',
    this.detail = '',
    this.createdAt,
  });

  factory TaskItem.fromJson(Object? raw) {
    final json = asMap(raw);
    final id = asString(json['id']);
    final runId = asString(json['run_id'], id);
    return TaskItem(
      id: id,
      runId: runId,
      task: asString(json['text'], asString(json['task'])),
      state: asString(json['state'], 'queued').toLowerCase(),
      turns: asInt(json['turns']),
      cost: asDouble(json['cost']),
      finish: asString(json['finish']),
      detail: asString(json['detail']),
      createdAt: asString(json['created_at']),
    );
  }

  final String id;
  final String runId;
  final String task;
  final String state;
  final int turns;
  final double? cost;
  final String finish;
  final String detail;
  final String? createdAt;

  bool get terminal =>
      const {'complete', 'interrupted', 'error', 'corrupt', 'done'}
          .contains(state);

  String get shortId {
    final value = id.isEmpty ? runId : id;
    return value.length <= 12 ? value : '…${value.substring(value.length - 8)}';
  }

  String get costLabel => cost == null ? '-' : '\$${cost!.toStringAsFixed(6)}';
}

class Snapshot {
  const Snapshot({
    required this.daemonState,
    required this.daemonDetail,
    required this.current,
    required this.last,
    required this.queue,
    required this.done,
    required this.totalCost,
    required this.version,
  });

  factory Snapshot.fromJson(Object? raw) {
    final json = asMap(raw);
    final daemon = asMap(json['daemon']);
    return Snapshot(
      daemonState: asString(daemon['state'], 'down').toLowerCase(),
      daemonDetail: asString(daemon['detail']),
      current: json['current'] == null
          ? null
          : TaskItem.fromJson(json['current']),
      last: json['last'] == null ? null : TaskItem.fromJson(json['last']),
      queue: [
        for (final row in asList(json['queue'])) TaskItem.fromJson(row),
      ],
      done: [
        for (final row in asList(json['done'])) TaskItem.fromJson(row),
      ],
      totalCost: asDouble(asMap(json['costs'])['total']),
      version: asInt(json['version']),
    );
  }

  static const empty = Snapshot(
    daemonState: 'down',
    daemonDetail: '',
    current: null,
    last: null,
    queue: [],
    done: [],
    totalCost: null,
    version: 0,
  );

  final String daemonState;
  final String daemonDetail;
  final TaskItem? current;
  final TaskItem? last;
  final List<TaskItem> queue;
  final List<TaskItem> done;
  final double? totalCost;
  final int version;

  bool get online => daemonState == 'running' || daemonState == 'starting';

  String get totalCostLabel =>
      totalCost == null ? '-' : '\$${totalCost!.toStringAsFixed(6)}';
}

class LogEntry {
  const LogEntry({
    required this.kind,
    this.turn = 0,
    this.name = '',
    this.args = '',
    this.obs = '',
    this.failed = false,
    this.result = '',
    this.finish = '',
    this.text = '',
    this.reason = '',
  });

  factory LogEntry.fromJson(Object? raw) {
    final json = asMap(raw);
    return LogEntry(
      kind: asString(json['kind'], 'pending'),
      turn: asInt(json['turn']),
      name: asString(json['name']),
      args: asString(json['args']),
      obs: asString(json['obs']),
      failed: asBool(json['failed']),
      result: asString(json['result']),
      finish: asString(json['finish']),
      text: asString(json['text']),
      reason: asString(json['reason']),
    );
  }

  final String kind;
  final int turn;
  final String name;
  final String args;
  final String obs;
  final bool failed;
  final String result;
  final String finish;
  final String text;
  final String reason;

  bool get isResult => kind == 'result';
  bool get isCall => kind == 'call';
}

class RunLog {
  const RunLog({
    required this.id,
    required this.state,
    required this.turns,
    required this.terminal,
    required this.entries,
  });

  factory RunLog.fromJson(Object? raw) {
    final json = asMap(raw);
    return RunLog(
      id: asString(json['id']),
      state: asString(json['state'], 'running').toLowerCase(),
      turns: asInt(json['turns']),
      terminal: asBool(json['terminal']),
      entries: [
        for (final row in asList(json['entries'])) LogEntry.fromJson(row),
      ],
    );
  }

  final String id;
  final String state;
  final int turns;
  final bool terminal;
  final List<LogEntry> entries;

  int get callCount => entries.where((entry) => entry.isCall).length;

  LogEntry? get summary {
    for (final entry in entries.reversed) {
      if (entry.isResult) return entry;
    }
    return null;
  }
}

class DirEntry {
  const DirEntry({required this.name, required this.path});

  factory DirEntry.fromJson(Object? raw) {
    final json = asMap(raw);
    final path = asString(json['path']);
    return DirEntry(
        name: asString(json['name'], path), path: path);
  }

  final String name;
  final String path;
}

class DirListing {
  const DirListing({
    required this.path,
    required this.parent,
    required this.roots,
    required this.dirs,
    required this.truncated,
  });

  factory DirListing.fromJson(Object? raw) {
    final json = asMap(raw);
    return DirListing(
      path: json['path'] == null ? null : asString(json['path']),
      parent: json['parent'] == null ? null : asString(json['parent']),
      roots: [
        for (final row in asList(json['roots'])) DirEntry.fromJson(row),
      ],
      dirs: [
        for (final row in asList(json['dirs'])) DirEntry.fromJson(row),
      ],
      truncated: asBool(json['truncated']),
    );
  }

  static const empty =
      DirListing(path: null, parent: null, roots: [], dirs: [], truncated: false);

  final String? path;
  final String? parent;
  final List<DirEntry> roots;
  final List<DirEntry> dirs;
  final bool truncated;
}
