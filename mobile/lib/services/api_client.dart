import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/types.dart';

const _baseUrl = String.fromEnvironment(
  'APEX_API_BASE_URL',
  defaultValue: 'http://localhost:8000/v1',
);

final dioProvider = Provider<Dio>((ref) {
  final dio = Dio(
    BaseOptions(
      baseUrl: _baseUrl,
      headers: {'X-User-Id': 'mobile-demo-user'},
      connectTimeout: const Duration(seconds: 5),
      receiveTimeout: const Duration(seconds: 5),
    ),
  );
  return dio;
});

final apiClientProvider = Provider<ApiClient>((ref) {
  return ApiClient(ref.watch(dioProvider));
});

class ApiClient {
  ApiClient(this._dio);

  final Dio _dio;

  Future<List<EventModel>> events() async {
    final response = await _dio.get<List<dynamic>>('/events');
    final data = response.data ?? [];
    return data
        .map((item) => EventModel.fromJson((item as Map).cast<String, dynamic>()))
        .toList();
  }

  Future<List<LeaderboardRowModel>> globalLeaderboard() async {
    final response = await _dio.get<Map<String, dynamic>>('/leaderboards/global');
    final rows = (response.data?['rows'] as List<dynamic>? ?? []);
    return rows
        .map((item) => LeaderboardRowModel.fromJson((item as Map).cast<String, dynamic>()))
        .toList();
  }
}
