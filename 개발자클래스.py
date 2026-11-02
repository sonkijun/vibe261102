#Developer라는 개발자 클래스를 정의하려고 함.
#soqndp id, title, skill 변수가 있고, 이 내용을 출려하는
#printInfo() 매서드가 필요해
class Developer:
    def __init__(self, id, title, skill):
        self.id = id
        self.title = title
        self.skill = skill

    def printInfo(self):
        print(f"ID: {self.id}, Title: {self.title}, Skill: {self.skill}")

    #인스턴스를 생성
    dev = Developer(1, "Backend Developer", "Python")     