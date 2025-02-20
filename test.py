from lib.MavenSearch2 import MavenSearcher
from lib.PomGenerator import PomGenerator

maven_search = MavenSearcher()
new_gen = PomGenerator()

find_result = maven_search.find_maven_package("flexmark-java", "0.42.14")
# new_dependency= maven_search.generate_pom_dependency(find_result)

print(find_result)

print(new_gen)

