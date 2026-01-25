"""
Performance testing and benchmarking for jobforge-ai with Azure OpenAI.
Tests response time, throughput, and cost efficiency.
"""

import time
import requests
import statistics
from dataclasses import dataclass
from typing import List
import json


@dataclass
class PerformanceMetrics:
    """Store performance metrics"""
    operation: str
    response_time_ms: float
    status_code: int
    tokens_used: int
    cost_usd: float


class PerformanceBenchmark:
    """Benchmark API performance"""
    
    BASE_URL = "http://localhost:8000"
    AZURE_COST_PER_1K_INPUT = 0.03
    AZURE_COST_PER_1K_OUTPUT = 0.06
    
    def __init__(self):
        self.metrics: List[PerformanceMetrics] = []
    
    def test_health_check(self, iterations: int = 10) -> None:
        """Benchmark health check endpoint"""
        print(f"\n🏥 Testing Health Check ({iterations} iterations)")
        print("-" * 50)
        
        times = []
        for i in range(iterations):
            start = time.time()
            response = requests.get(f"{self.BASE_URL}/health", timeout=10)
            elapsed = (time.time() - start) * 1000
            times.append(elapsed)
            
            status = "✅" if response.status_code == 200 else "❌"
            print(f"{status} Iteration {i+1}: {elapsed:.2f}ms")
        
        self._print_stats("Health Check", times)
    
    def test_api_endpoints(self) -> None:
        """Benchmark API endpoints"""
        print(f"\n🔧 Testing API Endpoints")
        print("-" * 50)
        
        endpoints = [
            ("/health", "GET", None),
            ("/docs", "GET", None),
            ("/openapi.json", "GET", None),
        ]
        
        for endpoint, method, data in endpoints:
            start = time.time()
            if method == "GET":
                response = requests.get(f"{self.BASE_URL}{endpoint}", timeout=10)
            else:
                response = requests.post(f"{self.BASE_URL}{endpoint}", json=data, timeout=10)
            
            elapsed = (time.time() - start) * 1000
            status = "✅" if response.status_code in [200, 201] else "❌"
            print(f"{status} {method} {endpoint}: {elapsed:.2f}ms")
    
    def test_job_parsing(self, num_jobs: int = 5) -> None:
        """Benchmark job parsing with Azure GPT-4"""
        print(f"\n📄 Testing Job Parsing ({num_jobs} jobs)")
        print("-" * 50)
        
        sample_job_desc = """
        Senior Software Engineer
        
        Requirements:
        - 5+ years Python experience
        - Strong understanding of AWS/Azure
        - Docker and Kubernetes knowledge
        - Microservices architecture
        - CI/CD pipelines
        - Team leadership
        
        We're looking for a talented engineer to join our team.
        """
        
        times = []
        costs = []
        
        for i in range(num_jobs):
            payload = {
                "job_description": sample_job_desc,
                "source": "linkedin"
            }
            
            start = time.time()
            try:
                response = requests.post(
                    f"{self.BASE_URL}/api/jobs/parse",
                    json=payload,
                    timeout=30
                )
                elapsed = (time.time() - start) * 1000
                times.append(elapsed)
                
                # Estimate cost (assuming ~300 tokens per job)
                estimated_tokens = 300
                cost = (estimated_tokens * self.AZURE_COST_PER_1K_INPUT) / 1000
                costs.append(cost)
                
                status = "✅" if response.status_code in [200, 201] else "❌"
                print(f"{status} Job {i+1}: {elapsed:.2f}ms | Est. cost: ${cost:.4f}")
            except requests.exceptions.Timeout:
                print(f"❌ Job {i+1}: TIMEOUT")
        
        if times:
            self._print_stats("Job Parsing", times)
            print(f"Total estimated cost: ${sum(costs):.4f}")
    
    def test_resume_analysis(self, num_resumes: int = 5) -> None:
        """Benchmark resume analysis with Azure GPT-4"""
        print(f"\n👤 Testing Resume Analysis ({num_resumes} resumes)")
        print("-" * 50)
        
        sample_resume = """
        John Doe
        Senior Software Engineer
        
        Experience:
        - 8 years Python development
        - 5 years AWS/Azure cloud
        - 3 years team leadership
        - Docker, Kubernetes expert
        - Microservices architecture
        
        Education:
        - BS Computer Science, Stanford
        - AWS Solutions Architect certified
        """
        
        times = []
        costs = []
        
        for i in range(num_resumes):
            payload = {
                "resume_text": sample_resume,
                "format": "text"
            }
            
            start = time.time()
            try:
                response = requests.post(
                    f"{self.BASE_URL}/api/resume/analyze",
                    json=payload,
                    timeout=30
                )
                elapsed = (time.time() - start) * 1000
                times.append(elapsed)
                
                # Estimate cost
                estimated_tokens = 500
                cost = (estimated_tokens * self.AZURE_COST_PER_1K_INPUT) / 1000
                costs.append(cost)
                
                status = "✅" if response.status_code in [200, 201] else "❌"
                print(f"{status} Resume {i+1}: {elapsed:.2f}ms | Est. cost: ${cost:.4f}")
            except requests.exceptions.Timeout:
                print(f"❌ Resume {i+1}: TIMEOUT")
        
        if times:
            self._print_stats("Resume Analysis", times)
            print(f"Total estimated cost: ${sum(costs):.4f}")
    
    def test_job_scoring(self, num_scores: int = 5) -> None:
        """Benchmark job to candidate scoring"""
        print(f"\n⭐ Testing Job Scoring ({num_scores} scores)")
        print("-" * 50)
        
        times = []
        
        for i in range(num_scores):
            payload = {
                "job_id": f"job_{i}",
                "candidate_id": f"candidate_{i}"
            }
            
            start = time.time()
            try:
                response = requests.post(
                    f"{self.BASE_URL}/api/jobs/score",
                    json=payload,
                    timeout=30
                )
                elapsed = (time.time() - start) * 1000
                times.append(elapsed)
                
                status = "✅" if response.status_code in [200, 201] else "❌"
                print(f"{status} Score {i+1}: {elapsed:.2f}ms")
            except requests.exceptions.Timeout:
                print(f"❌ Score {i+1}: TIMEOUT")
        
        if times:
            self._print_stats("Job Scoring", times)
    
    def test_concurrent_requests(self, num_concurrent: int = 10) -> None:
        """Test concurrent request handling"""
        import concurrent.futures
        
        print(f"\n🔄 Testing Concurrent Requests ({num_concurrent} parallel)")
        print("-" * 50)
        
        def make_request():
            start = time.time()
            try:
                response = requests.get(f"{self.BASE_URL}/health", timeout=10)
                return (time.time() - start) * 1000, response.status_code
            except Exception as e:
                return None, str(e)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_concurrent) as executor:
            futures = [executor.submit(make_request) for _ in range(num_concurrent)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        times = [t for t, status in results if t is not None]
        if times:
            self._print_stats("Concurrent Requests", times)
            success_rate = len(times) / num_concurrent * 100
            print(f"Success rate: {success_rate:.1f}%")
    
    def test_database_queries(self) -> None:
        """Benchmark database query performance"""
        print(f"\n💾 Testing Database Queries")
        print("-" * 50)
        
        import docker
        
        try:
            client = docker.from_env()
            postgres = client.containers.get("jobforge-postgres")
            
            # Test basic query
            start = time.time()
            result = postgres.exec_run(
                "psql -U postgres -d jobforge_ai -c 'SELECT COUNT(*) FROM artifact;'"
            )
            elapsed = (time.time() - start) * 1000
            
            print(f"✅ Count query: {elapsed:.2f}ms")
            
            # Test complex query
            start = time.time()
            result = postgres.exec_run(
                "psql -U postgres -d jobforge_ai -c 'SELECT * FROM artifact LIMIT 100;'"
            )
            elapsed = (time.time() - start) * 1000
            
            print(f"✅ Range query: {elapsed:.2f}ms")
        except Exception as e:
            print(f"❌ Database test failed: {e}")
    
    def test_redis_performance(self) -> None:
        """Benchmark Redis cache performance"""
        print(f"\n⚡ Testing Redis Performance")
        print("-" * 50)
        
        import redis
        
        try:
            r = redis.Redis(host='localhost', port=6379, password='redis_password')
            
            # Test write performance
            start = time.time()
            for i in range(100):
                r.set(f"test_key_{i}", f"value_{i}")
            write_time = (time.time() - start) * 1000
            
            print(f"✅ Write 100 keys: {write_time:.2f}ms")
            
            # Test read performance
            start = time.time()
            for i in range(100):
                r.get(f"test_key_{i}")
            read_time = (time.time() - start) * 1000
            
            print(f"✅ Read 100 keys: {read_time:.2f}ms")
            
            # Cleanup
            for i in range(100):
                r.delete(f"test_key_{i}")
        except Exception as e:
            print(f"❌ Redis test failed: {e}")
    
    def _print_stats(self, operation: str, times: List[float]) -> None:
        """Print statistics for a set of measurements"""
        if not times:
            return
        
        avg = statistics.mean(times)
        median = statistics.median(times)
        min_t = min(times)
        max_t = max(times)
        stdev = statistics.stdev(times) if len(times) > 1 else 0
        
        print(f"\n📊 Statistics for {operation}:")
        print(f"  Average:  {avg:.2f}ms")
        print(f"  Median:   {median:.2f}ms")
        print(f"  Min:      {min_t:.2f}ms")
        print(f"  Max:      {max_t:.2f}ms")
        print(f"  StdDev:   {stdev:.2f}ms")
    
    def run_full_benchmark(self) -> None:
        """Run complete performance benchmark"""
        print("\n" + "="*60)
        print("🚀 JOBFORGE-AI PERFORMANCE BENCHMARK")
        print("="*60)
        
        self.test_health_check(iterations=10)
        self.test_api_endpoints()
        self.test_database_queries()
        self.test_redis_performance()
        self.test_job_parsing(num_jobs=3)
        self.test_resume_analysis(num_resumes=3)
        self.test_job_scoring(num_scores=3)
        self.test_concurrent_requests(num_concurrent=5)
        
        print("\n" + "="*60)
        print("✅ Benchmark Complete!")
        print("="*60)


if __name__ == "__main__":
    benchmark = PerformanceBenchmark()
    benchmark.run_full_benchmark()
