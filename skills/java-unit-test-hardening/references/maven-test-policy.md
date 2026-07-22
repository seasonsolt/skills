# Maven Test Policy

This is an internal reference. Localize human-facing report content before materializing it. Prefer the repository's `./mvnw`; use `mvn` only when no wrapper exists.

## Lifecycle Contract

| Lane | Command | Docker | Required behavior |
| --- | --- | --- | --- |
| Developer/unit | `<maven> test` | No | Run all Surefire `*Test` tests |
| Release build | `<maven> clean package`, `install`, or `deploy` | No | Run unit tests; do not load Testcontainers |
| Integration gate | `<maven> clean verify -Pintegration-tests` | Yes | Run unit tests and all Failsafe `*IT` tests |

The integration gate is mandatory when the repository already defines it, the selected workflow adds `*IT` tests, or an in-scope behavior requires a real database or external infrastructure. A unit-only workflow may mark it `not applicable` only with evidence that the repository has no integration profile, no `*IT` sources, and no in-scope integration scenario. Do not create an empty profile solely to satisfy a closure checklist, and never treat missing Docker as evidence of non-applicability.

## 本地反馈循环

RED/GREEN 期间不得运行整仓 `clean verify`。优先使用目标仓库已经支持的最窄命令：

```bash
<maven> -pl <module> -am -Dtest=<TestClass>#<method> test
<maven> -pl <module> -am -Dtest=<TestClass> test
<maven> -pl <module> -am -Dit.test=<ITClass> verify -Pintegration-tests
```

最终证据仍需一次完整 Dockerless lane，以及适用时一次干净 integration lane。只有目标仓库已经提供经过验证的 unit-skip 属性时，integration job 才可使用该属性避免重复 Surefire；禁止临时用 `skipTests` 同时跳过 Failsafe。

Bind `maven-failsafe-plugin` only inside the `integration-tests` profile. This is clearer than globally binding Failsafe and relying on a default skip property.

```xml
<profiles>
    <profile>
        <id>integration-tests</id>
        <build>
            <plugins>
                <plugin>
                    <groupId>org.apache.maven.plugins</groupId>
                    <artifactId>maven-failsafe-plugin</artifactId>
                    <version>${maven-failsafe-plugin.version}</version>
                    <executions>
                        <execution>
                            <goals>
                                <goal>integration-test</goal>
                                <goal>verify</goal>
                            </goals>
                        </execution>
                    </executions>
                </plugin>
            </plugins>
        </build>
    </profile>
</profiles>
```

## CI Contract

Changing CI is outside the default test-only mutation scope. When the campaign PRD does not explicitly authorize CI edits, record the following as a manual integration requirement instead of modifying pipeline files.

Use two mandatory jobs:

1. `unit-build`: run the default release command on a normal JDK runner without requiring Docker.
2. `integration-gate`: run `verify -Pintegration-tests` on a runner with a verified Docker daemon.

The release must consume the same commit and preferably promote the artifact produced after both jobs pass. Do not rebuild an unverified revision. Cache Maven artifacts and container images for speed, but never cache test results as proof for a different commit.

## Failure Semantics

The integration profile is an explicit promise that Docker is available. If Docker discovery, image startup, schema initialization, or a test fails, the job must fail. Do not annotate mandatory Testcontainers tests with `disabledWithoutDocker = true` and do not catch Docker initialization failures.

For local development, developers choose whether to activate the profile. For CI, the pipeline chooses a compatible runner; the tests do not choose to disappear.

## JDK 21 Mockito Agent

Mockito inline mocking currently may dynamically attach Byte Buddy. Some hardened runners prohibit self-attachment, and newer JDKs warn that dynamic agent loading will be disabled by default. If this occurs outside a sandbox, configure Byte Buddy or Mockito as a startup `-javaagent` while preserving JaCoCo's `argLine`; do not weaken runner security globally without review.

## Testcontainers Runtime Options

Prefer a local Docker-compatible daemon on the quality runner. OrbStack, Docker Desktop, Colima, and standard Linux Docker are acceptable when their socket is configured. A remote Docker daemon or managed Testcontainers service is also valid if credentials and isolation meet project policy.

## Testcontainers Version Resolution

Do not encode a time-sensitive universal version floor. First inspect the target repository's parent POM, imported BOMs, declared dependencies, Docker runtime, and the actually resolved `org.testcontainers` plus `docker-java` family:

```bash
<maven> dependency:list -DincludeGroupIds=org.testcontainers,com.github.docker-java
<maven> dependency:tree -Dincludes=org.testcontainers:*,com.github.docker-java:*
```

If a reproducible client/server incompatibility exists, use systematic debugging to identify the incompatible resolved member. Prefer the repository or framework BOM's coherent release line; when an override is necessary, align every affected family member to one compatible line and keep it test-scoped. Re-run both commands and capture the Testcontainers startup version as evidence. Never infer success from declared versions alone, and never add an override preemptively because another repository once needed one.
