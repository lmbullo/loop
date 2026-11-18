/// The mobile client protocol: private-network HTTP with a bearer token.
///
/// The client is deliberately thin.  It validates that the configured host is
/// loopback, RFC1918/ULA/link-local or a Tailscale 100.64.0.0/10 address before
/// opening a socket, then asks the server for snapshots, directories, queue
/// submissions and run logs.
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'models.dart';

enum ApiFailure { auth, network, protocol, server, local }

class LoopApiException implements Exception {
  const LoopApiException(this.kind, this.message);

  final ApiFailure kind;
  final String message;

  @override
  String toString() => message;
}

abstract class LoopApi {
  Future<Map<String, dynamic>> health();
  Future<Map<String, dynamic>> dirs([String? path]);
  Future<Map<String, dynamic>> workspaces();
  Future<Map<String, dynamic>> startWorkspace(String root);
  Future<Map<String, dynamic>> snapshot([String? root]);
  Future<Map<String, dynamic>> enqueue(String task, String root);
  Future<Map<String, dynamic>> runLog(String runId);
  void close();
}

bool isLocalAddress(InternetAddress address) {
  final bytes = address.rawAddress;
  if (address.type == InternetAddressType.IPv4 && bytes.length == 4) {
    final a = bytes[0];
    final b = bytes[1];
    return a == 10 ||
        a == 127 ||
        (a == 100 && b >= 64 && b <= 127) ||
        (a == 169 && b == 254) ||
        (a == 172 && b >= 16 && b <= 31) ||
        (a == 192 && b == 168);
  }
  if (address.type == InternetAddressType.IPv6 && bytes.length == 16) {
    final loopback =
        bytes.take(15).every((value) => value == 0) && bytes[15] == 1;
    final linkLocal = bytes[0] == 0xfe && (bytes[1] & 0xc0) == 0x80;
    final ula = (bytes[0] & 0xfe) == 0xfc;
    return loopback || linkLocal || ula;
  }
  return false;
}

Future<String> validateLocalHost(String host) async {
  var value = host.trim();
  if (value.startsWith('[') && value.endsWith(']')) {
    value = value.substring(1, value.length - 1);
  }
  if (value.isEmpty) {
    throw const LoopApiException(ApiFailure.local, 'host is required');
  }
  final literal = InternetAddress.tryParse(value);
  if (literal != null) {
    if (!isLocalAddress(literal)) {
      throw const LoopApiException(
        ApiFailure.local,
        'host must be a private, loopback or Tailscale address',
      );
    }
    return value;
  }
  if (value.toLowerCase() == 'localhost') return 'localhost';
  List<InternetAddress> addresses;
  try {
    addresses = await InternetAddress.lookup(value);
  } on SocketException {
    throw LoopApiException(ApiFailure.network, 'cannot resolve host $value');
  }
  if (addresses.isEmpty || !addresses.every(isLocalAddress)) {
    throw const LoopApiException(
      ApiFailure.local,
      'host must resolve to private, loopback or Tailscale addresses',
    );
  }
  return value;
}

class HttpLoopApi implements LoopApi {
  HttpLoopApi(this.settings, {HttpClient? client})
    : _client = client ?? HttpClient() {
    _client.connectionTimeout = const Duration(seconds: 5);
  }

  final ConnectionSettings settings;
  final HttpClient _client;
  static const _timeout = Duration(seconds: 12);

  Uri _uri(String path, [Map<String, String>? query]) => Uri(
    scheme: 'http',
    host: settings.host,
    port: settings.port,
    path: path,
    queryParameters: query,
  );

  Future<Map<String, dynamic>> _request(
    String method,
    String path, {
    Map<String, String>? query,
    Map<String, dynamic>? body,
  }) async {
    HttpClientRequest request;
    HttpClientResponse response;
    String text;
    try {
      request = await _client
          .openUrl(method, _uri(path, query))
          .timeout(_timeout);
      request.headers.set(
        HttpHeaders.authorizationHeader,
        'Bearer ${settings.token}',
      );
      request.headers.set(HttpHeaders.acceptHeader, 'application/json');
      if (body != null) {
        final raw = utf8.encode(jsonEncode(body));
        request.headers.contentType = ContentType.json;
        request.headers.contentLength = raw.length;
        request.add(raw);
      }
      response = await request.close().timeout(_timeout);
      text = await utf8.decoder.bind(response).join().timeout(_timeout);
    } on TimeoutException {
      throw const LoopApiException(ApiFailure.network, 'connection timed out');
    } on SocketException catch (error) {
      throw LoopApiException(ApiFailure.network, error.message);
    } on HttpException catch (error) {
      throw LoopApiException(ApiFailure.network, error.message);
    }
    Map<String, dynamic> data;
    try {
      data = text.trim().isEmpty
          ? <String, dynamic>{}
          : asMap(jsonDecode(text));
    } on FormatException {
      throw const LoopApiException(
        ApiFailure.protocol,
        'server returned non-JSON data',
      );
    }
    if (response.statusCode == HttpStatus.unauthorized) {
      throw const LoopApiException(ApiFailure.auth, 'invalid token');
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      final detail = asString(data['text'], 'HTTP ${response.statusCode}');
      throw LoopApiException(ApiFailure.server, detail);
    }
    if (data['ok'] == false) {
      throw LoopApiException(
        ApiFailure.server,
        asString(data['text'], 'server rejected request'),
      );
    }
    return data;
  }

  @override
  Future<Map<String, dynamic>> health() => _request('GET', '/v1/health');

  @override
  Future<Map<String, dynamic>> dirs([String? path]) => _request(
    'GET',
    '/v1/dirs',
    query: path == null || path.isEmpty ? null : {'path': path},
  );

  @override
  Future<Map<String, dynamic>> workspaces() => _request('GET', '/v1/workspaces');

  @override
  Future<Map<String, dynamic>> startWorkspace(String root) =>
      _request('POST', '/v1/workspaces/start', body: {'root': root});

  @override
  Future<Map<String, dynamic>> snapshot([String? root]) => _request(
        'GET',
        '/v1/snapshot',
        query: root == null || root.isEmpty ? null : {'root': root},
      );

  @override
  Future<Map<String, dynamic>> enqueue(String task, String root) =>
      _request('POST', '/v1/tasks', body: {'task': task, 'root': root});

  @override
  Future<Map<String, dynamic>> runLog(String runId) =>
      _request('GET', '/v1/runs/${Uri.encodeComponent(runId)}');

  @override
  void close() => _client.close(force: true);
}
